#include "CatrunElevatorTransition.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "CatrunExitTransitionComponent.h"
#include "CatrunElevatorWeightComponent.h"
#include "CatrunLevelFlow.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/DecalComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponentBase.h"
#include "Components/LocalFogVolumeComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/TriggerBox.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Rendering/DrawElements.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Perception/CatrunGroundSupport.h"
#include "Settings/CatrunInputBindings.h"
#include "Sound/CatrunNotice.h"
#include "Sound/SoundBase.h"
#include "Styling/CoreStyle.h"
#include "UI/CatrunMinimapWidget.h"
#include "Widgets/SLeafWidget.h"

DEFINE_LOG_CATEGORY_STATIC(LogCatrunElevator, Log, All);

namespace
{
    constexpr float AlignSeconds = .24f;
    constexpr float DepartureAlignSeconds = 1.f;
    // Cuts inside the continuous PeekLoafIn clip: approach | floor shot | edge, walk inside, loaf.
    constexpr float PeekShotStartSeconds = 74.f / 30.f;
    constexpr float PeekShotEndSeconds = 178.f / 30.f;
    constexpr int32 PeekClipIndex = 5;
    constexpr int32 RideClipIndex = 6;
    constexpr float RideSeconds = 3.6f;
    constexpr float RiseEaseSeconds = 1.6f;
    constexpr float BlackoutSeconds = .65f;
    constexpr float ApproachSeconds = .95f;
    constexpr float LoafReadSeconds = 1.25f;
    constexpr float LatchClipLeadIn = 36.f / 30.f;
    constexpr float LatchClipImpact = 37.f / 30.f;
    constexpr float StartImpact = 8.f / 30.f;
    constexpr float MaxLetterboxFraction = .102f;
    constexpr int32 ArrivalWalkClipIndex = 2;
    constexpr int32 ArrivalLookClipIndex = 3;
    constexpr float FallbackLookSeconds = 1.15f;

    bool MatchesCatSkeleton(const UAnimSequence* Clip, const ACharacter& Pawn)
    {
        const auto* Mesh = Pawn.GetMesh();
        const auto* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
        return IsValid(Clip) && Asset && Clip->GetSkeleton() == Asset->GetSkeleton() && Clip->GetPlayLength() > 0.f;
    }

    class SElevatorLetterbox : public SLeafWidget
    {
    public:
        SLATE_BEGIN_ARGS(SElevatorLetterbox) {}
            SLATE_ATTRIBUTE(float, Fraction)
        SLATE_END_ARGS()

        void Construct(const FArguments& Args) { Fraction = Args._Fraction; }
        virtual FVector2D ComputeDesiredSize(float LayoutScaleMultiplier) const override { return FVector2D::ZeroVector; }
        virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& Culling,
            FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool bParentEnabled) const override
        {
            const FVector2f Size(Geometry.GetLocalSize());
            const float Height = Fraction.Get() * Size.Y;
            if (Height <= 0.f) return Layer;
            const FSlateBrush* Brush = FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"));
            const FVector2f BarSize(Size.X, Height);
            FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(BarSize, FSlateLayoutTransform()),
                Brush, ESlateDrawEffect::None, FLinearColor::Black);
            FSlateDrawElement::MakeBox(Elements, Layer,
                Geometry.ToPaintGeometry(BarSize, FSlateLayoutTransform(FVector2f(0.f, Size.Y - Height))),
                Brush, ESlateDrawEffect::None, FLinearColor::Black);
            return Layer;
        }
    private:
        TAttribute<float> Fraction;
    };

    bool ContainsCenter(const ATriggerBox* Volume, const APawn& Pawn)
    {
        const auto* Box = Volume ? Cast<UBoxComponent>(Volume->GetCollisionComponent()) : nullptr;
        if (!Box) return false;
        const FVector Local = Box->GetComponentTransform().InverseTransformPosition(Pawn.GetActorLocation()).GetAbs();
        const FVector Extent = Box->GetUnscaledBoxExtent();
        return Local.X <= Extent.X && Local.Y <= Extent.Y && Local.Z <= Extent.Z;
    }

    bool IsUsableCamera(const AActor* Camera)
    {
        return IsValid(Camera) && Camera->FindComponentByClass<UCameraComponent>();
    }

    bool IsLiveEndPlay(const UWorld* World, EEndPlayReason::Type Reason)
    {
        return World && !World->bIsTearingDown && Reason != EEndPlayReason::LevelTransition
            && Reason != EEndPlayReason::EndPlayInEditor && Reason != EEndPlayReason::Quit;
    }
}

ACatrunElevatorTransition::ACatrunElevatorTransition()
{
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    ExitTransition = CreateDefaultSubobject<UCatrunExitTransitionComponent>(TEXT("ExitTransition"));
    CabinWeight = CreateDefaultSubobject<UCatrunElevatorWeightComponent>(TEXT("CabinWeight"));
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    SkipKey = EKeys::SpaceBar;
}

void ACatrunElevatorTransition::BeginPlay()
{
    Super::BeginPlay();
    ExitTransition->OnTravelFailed.AddDynamic(this, &ACatrunElevatorTransition::HandleTravelFailure);
    if (bArrivalSide)
    {
        auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
        bArrivalExpected = Flow && Flow->ClaimElevatorArrival(*this);
        if (!bArrivalExpected)
        {
            State = ECatrunElevatorState::Finished;
            StartCabinWeight();
        }
    }
    else if (auto* Marks = UCatrunMarkSubsystem::Get(this))
        Marks->ObserveElevatorCorridor(*this);
    if (IsUsableCamera(WarehouseCamera))
    {
        WarehouseCamera->Tags.AddUnique(TEXT("CatrunGameplayCamera"));
        WarehouseCamera->Tags.AddUnique(TEXT("CatrunElevatorWarehouseCamera"));
        WarehouseCameraRest = WarehouseCamera->GetActorTransform();
        WarehouseCameraRestFOV = WarehouseCamera->FindComponentByClass<UCameraComponent>()->FieldOfView;
    }
}

void ACatrunElevatorTransition::EndPlay(const EEndPlayReason::Type Reason)
{
    if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->LeaveElevatorCorridor(*this);
    ExitTransition->OnTravelFailed.RemoveDynamic(this, &ACatrunElevatorTransition::HandleTravelFailure);
    if (IsLiveEndPlay(GetWorld(), Reason)) CancelTransition();
    else RestorePresentation();
    RestoreCabinIsolation();
    RestoreMinimap();
    UpdateOccluders(false, false);
    SetLocalLighting(nullptr);
    if (IsLiveEndPlay(GetWorld(), Reason)) UpdateWarehouseView(nullptr, nullptr, false);
    if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->ReleaseElevatorArrival(*this);
    Super::EndPlay(Reason);
}

bool ACatrunElevatorTransition::IsInsideCorridor(const APawn& Pawn) const
{
    return !bArrivalSide && !IsActorBeingDestroyed() && Pawn.GetWorld() == GetWorld()
        && (ContainsCenter(CorridorVolume, Pawn) || ContainsCenter(WarehouseVolume, Pawn) || ContainsCenter(CabinVolume, Pawn));
}

void ACatrunElevatorTransition::StartCabinWeight(ACharacter* ScriptedRider)
{
    if (!bArrivalSide) return;
    CabinWeight->SetScriptedRider(ScriptedRider);
    if (CabinWeight->IsResponding()) return;
    CabinWeight->StartResponse();
    if (CabinWeight->IsResponding()) AddTickPrerequisiteComponent(CabinWeight);
}

void ACatrunElevatorTransition::SetLocalLighting(USkeletalMeshComponent* Mesh)
{
    if (Mesh == LitMesh.Get()) return;
    if (auto* Previous = LitMesh.Get())
        Previous->SetLightingChannels(PreviousLighting.bChannel0, PreviousLighting.bChannel1, PreviousLighting.bChannel2);
    LitMesh = Mesh;
    if (Mesh)
    {
        PreviousLighting = Mesh->LightingChannels;
        Mesh->SetLightingChannels(false, true, false);
    }
}

void ACatrunElevatorTransition::UpdateWarehouseView(ACharacter* Pawn, APlayerController* PC, bool bWarehouse)
{
    if (auto* WarehouseOwner = WarehouseController.Get(); WarehouseOwner && (!bWarehouse || WarehouseOwner != PC || Pawn != WarehousePawn.Get()))
    {
        if (PreviousWarehouseView.IsValid() && (WarehouseOwner->GetViewTarget() == WarehouseCamera
            || (WarehouseOwner->PlayerCameraManager && WarehouseOwner->PlayerCameraManager->PendingViewTarget.Target == WarehouseCamera)))
            WarehouseOwner->SetViewTargetWithBlend(PreviousWarehouseView.Get(), .35f);
        PreviousWarehouseView.Reset();
        WarehouseController.Reset();
        WarehousePawn.Reset();
    }
    if (!bWarehouse || !PC || PC->IsMoveInputIgnored() || !IsUsableCamera(WarehouseCamera)
        || WarehouseController.IsValid() || !PC->PlayerCameraManager || PC->PlayerCameraManager->PendingViewTarget.Target) return;
    AActor* Previous = PC->GetViewTarget();
    if (!IsUsableCamera(Previous) || Previous == WarehouseCamera || UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this)) return;
    PreviousWarehouseView = Previous;
    WarehouseController = PC;
    WarehousePawn = Pawn;
    PC->SetViewTargetWithBlend(WarehouseCamera, .35f);
}

void ACatrunElevatorTransition::UpdateWarehouseFraming(bool bCabin, float DeltaSeconds)
{
    if (bArrivalSide || WarehouseCameraRestFOV <= 0.f || !IsUsableCamera(WarehouseCamera)) return;
    const float Previous = WarehouseFraming;
    WarehouseFraming = FMath::FInterpTo(WarehouseFraming, bCabin ? 1.f : 0.f, DeltaSeconds, 3.2f);
    if (WarehouseFraming < .002f) WarehouseFraming = 0.f;
    if (Previous == WarehouseFraming) return;
    const FVector Cabin = (CabinPivot ? CabinPivot->GetActorLocation() : GetActorLocation()) + FVector::UpVector * 130.;
    const FQuat Aim = (Cabin - WarehouseCameraRest.GetLocation()).Rotation().Quaternion();
    WarehouseCamera->SetActorRotation(FQuat::Slerp(WarehouseCameraRest.GetRotation(), Aim, WarehouseFraming));
    WarehouseCamera->FindComponentByClass<UCameraComponent>()->SetFieldOfView(FMath::Lerp(WarehouseCameraRestFOV, 48.f, WarehouseFraming));
}

void ACatrunElevatorTransition::UpdateOccluders(bool bCorridor, bool bCabin, bool bAscent)
{
    const auto ShouldHide = [this, bCorridor, bCabin, bAscent](AActor* Actor)
    {
        return (bCorridor && CorridorOccluders.Contains(Actor)) || (bCabin && CabinOccluders.Contains(Actor))
            || (bAscent && HideDuringAscent.Contains(Actor));
    };
    for (int32 Index = HiddenOccluders.Num() - 1; Index >= 0; --Index)
    {
        AActor* Actor = HiddenOccluders[Index].Get();
        if (Actor && ShouldHide(Actor)) continue;
        if (Actor) Actor->SetActorHiddenInGame(false);
        HiddenOccluders.RemoveAtSwap(Index);
    }
    const auto Hide = [this](const TArray<TObjectPtr<AActor>>& Actors)
    {
        for (AActor* Actor : Actors)
        {
            if (!IsValid(Actor) || Actor->IsHidden()) continue;
            Actor->SetActorHiddenInGame(true);
            HiddenOccluders.Add(Actor);
        }
    };
    if (bCorridor) Hide(CorridorOccluders);
    if (bCabin) Hide(CabinOccluders);
    if (bAscent) Hide(HideDuringAscent);
}

void ACatrunElevatorTransition::UpdateFreeWalk(ACharacter* Pawn, APlayerController* PC, float DeltaSeconds)
{
    const bool bCabin = Pawn && ContainsCenter(CabinVolume, *Pawn);
    const bool bWarehouse = Pawn && ContainsCenter(WarehouseVolume, *Pawn);
    UpdateZonePresentation(Pawn, PC, DeltaSeconds);
    UpdateWarehouseView(Pawn, PC, bWarehouse || bCabin);
    UpdateWarehouseFraming(bCabin, DeltaSeconds);
    if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->RefreshCorridor();
    if (!Pawn || !PC || PC->IsMoveInputIgnored() || !PC->PlayerCameraManager || PC->PlayerCameraManager->PendingViewTarget.Target
        || !bCabin || !ContainsCenter(EntryVolume, *Pawn))
    {
        PromptCooldown = 0.f;
        return;
    }
    const FKey Interact = UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Interact);
    PromptCooldown -= DeltaSeconds;
    if (PromptCooldown <= 0.f)
    {
        if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
            Notice->ShowNotice(FText::Format(NSLOCTEXT("Catrun", "ElevatorPullHint", "[{0}] 승강기 고리 당기기"), Interact.GetDisplayName()), 1.9f);
        PromptCooldown = 1.7f;
    }
    if (PC->WasInputKeyJustPressed(Interact)) TryBegin(Pawn);
}

void ACatrunElevatorTransition::UpdateZonePresentation(ACharacter* Pawn, APlayerController* PC, float DeltaSeconds)
{
    const bool bCabin = Pawn && ContainsCenter(CabinVolume, *Pawn);
    const bool bCorridor = Pawn && ContainsCenter(CorridorVolume, *Pawn);
    const bool bWarehouse = Pawn && ContainsCenter(WarehouseVolume, *Pawn);
    const bool bElevatorZone = bCabin || bCorridor || bWarehouse || (Pawn && ContainsCenter(EntryVolume, *Pawn));
    UpdateOccluders(bCorridor, bCabin);
    UpdateCabinIsolation(Pawn, PC, bCabin);
    if (bElevatorZone) HideMinimap(PC, DeltaSeconds);
    else RestoreMinimap();
    SetLocalLighting(bUseLocalElevatorLighting && bElevatorZone ? Pawn->GetMesh() : nullptr);
}

bool ACatrunElevatorTransition::IsIsolationVisibleActor(const AActor* Actor) const
{
    // Keep attached cabin details and the existing cat's attachments without relying on actor labels.
    for (const AActor* Part = Actor; Part; Part = Part->GetAttachParentActor())
        if (Part == this || Part == IsolationCat.Get() || Part == CabinPivot || Part == ChainActor
            || Part == LanternActor || CabinActors.Contains(Part) || ControlPullActors.Contains(Part)
            || LanternActors.Contains(Part) || Part->ActorHasTag(TEXT("CatrunElevatorIsolationVisible"))
            || Part->FindComponentByClass<UCameraComponent>()) return true;
    return Actor && IsolationCat.IsValid() && Actor->IsOwnedBy(IsolationCat.Get());
}

void ACatrunElevatorTransition::IsolateActor(AActor* Actor)
{
    auto* PC = IsolationController.Get();
    if (!PC || !IsValid(Actor) || Actor->GetWorld() != GetWorld() || IsIsolationVisibleActor(Actor)) return;

    TInlineComponentArray<USceneComponent*> Components;
    Actor->GetComponents(Components);
    for (auto* Component : Components)
    {
        if (auto* Primitive = Cast<UPrimitiveComponent>(Component))
        {
            // The local view hides geometry while collision, AI and actor visibility remain unchanged.
            if (!PC->HiddenPrimitiveComponents.Contains(Primitive))
            {
                PC->HiddenPrimitiveComponents.Add(Primitive);
                IsolatedPrimitives.Add(Primitive);
            }
        }
        else if (!Actor->IsHidden() && Component->GetVisibleFlag() && !Component->bHiddenInGame
            && (Component->IsA<ULightComponentBase>() || Component->IsA<USkyAtmosphereComponent>()
                || Component->IsA<UExponentialHeightFogComponent>() || Component->IsA<ULocalFogVolumeComponent>()
                || Component->IsA<UVolumetricCloudComponent>() || Component->IsA<UDecalComponent>()))
        {
            // These renderers are not primitives. Only take ownership of an initially visible component.
            Component->SetHiddenInGame(true);
            IsolatedSceneComponents.Add(Component);
        }
    }
}

void ACatrunElevatorTransition::UpdateCabinIsolation(ACharacter* Pawn, APlayerController* PC, bool bIsolate)
{
    if (!bIsolate || bArrivalSide || !Pawn || !PC || !PC->IsLocalController())
    {
        RestoreCabinIsolation();
        return;
    }
    if (IsolationController.Get() == PC && IsolationCat.Get() == Pawn) return;
    RestoreCabinIsolation();
    IsolationController = PC;
    IsolationCat = Pawn;
    IsolationSpawnedHandle = GetWorld()->AddOnActorSpawnedHandler(
        FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::IsolateActor));
    // Include the original map actors as well as the authored HideDuringAscent list.
    for (TActorIterator<AActor> It(GetWorld()); It; ++It) IsolateActor(*It);
}

void ACatrunElevatorTransition::RestoreCabinIsolation()
{
    if (auto* World = GetWorld(); World && IsolationSpawnedHandle.IsValid())
        World->RemoveOnActorSpawnedHandler(IsolationSpawnedHandle);
    IsolationSpawnedHandle.Reset();
    if (auto* PC = IsolationController.Get())
        for (const auto& Primitive : IsolatedPrimitives) PC->HiddenPrimitiveComponents.RemoveSingleSwap(Primitive);
    for (const auto& Component : IsolatedSceneComponents)
        if (auto* Scene = Component.Get(); Scene && Scene->bHiddenInGame) Scene->SetHiddenInGame(false);
    IsolatedPrimitives.Reset();
    IsolatedSceneComponents.Reset();
    IsolationController.Reset();
    IsolationCat.Reset();
}

bool ACatrunElevatorTransition::ValidateClips(const ACharacter& Pawn) const
{
    const auto& Clips = bArrivalSide ? ArrivalClips : DepartureClips;
    if (Clips.Num() != (bArrivalSide ? 2 : 7)) return false;
    for (const UAnimSequence* Clip : Clips)
        if (CinematicMesh ? (!IsValid(Clip) || Clip->GetSkeleton() != CinematicMesh->GetSkeleton() || Clip->GetPlayLength() <= 0.f)
            : !MatchesCatSkeleton(Clip, Pawn)) return false;
    return true;
}

void ACatrunElevatorTransition::WearCinematicMesh(ACharacter& Pawn)
{
    auto* Mesh = Pawn.GetMesh();
    if (!CinematicMesh || Mesh->GetSkeletalMeshAsset() == CinematicMesh) return;
    PlayMesh = Mesh->GetSkeletalMeshAsset();
    PlayMaterials = Mesh->OverrideMaterials;
    Mesh->EmptyOverrideMaterials();
    Mesh->SetSkeletalMeshAsset(CinematicMesh);
    // The play cat's AnimBP cannot drive this skeleton: hold the first cinematic pose through the alignment.
    ActiveClip = (bArrivalSide ? ArrivalClips : DepartureClips)[0];
    Mesh->PlayAnimation(ActiveClip, false);
    if (auto* Single = Mesh->GetSingleNodeInstance())
    {
        Single->SetRootMotionMode(ERootMotionMode::NoRootMotionExtraction);
        Single->SetPlaying(false);
        Single->SetPosition(0.f, false);
    }
    bOwnPlayback = true;
}

void ACatrunElevatorTransition::SavePresentation(ACharacter& Pawn, APlayerController& PC)
{
    Cat = &Pawn;
    Controller = &PC;
    GameplayCamera = PC.GetViewTarget();
    AlignStart = Pawn.GetActorLocation();
    AlignStartRotation = Pawn.GetActorQuat();
    auto* Mesh = Pawn.GetMesh();
    OriginalMeshRelative = Mesh->GetRelativeTransform();
    SavedAnimClass = Mesh->GetAnimClass();
    SavedAnimMode = Mesh->GetAnimationMode();
    SavedAnimation = Mesh->AnimationData;
    if (auto* Single = Mesh->GetSingleNodeInstance())
    {
        SavedAnimation.AnimToPlay = Single->GetCurrentAsset();
        SavedAnimation.SavedPosition = Single->GetCurrentTime();
        SavedAnimation.SavedPlayRate = Single->GetPlayRate();
        SavedAnimation.bSavedLooping = Single->IsLooping();
        SavedAnimation.bSavedPlaying = Single->IsPlaying();
    }
    MotionPivot = CabinPivot ? CabinPivot->GetActorLocation() : CatMark->GetActorLocation();
    LanternPivot = LanternActor ? LanternActor->GetActorLocation() : MotionPivot;
    const auto SaveActor = [this](AActor* Actor)
    {
        if (IsValid(Actor)) RestTransforms.FindOrAdd(Actor, Actor->GetActorTransform());
    };
    for (AActor* Actor : CabinActors) SaveActor(Actor);
    for (AActor* Actor : ControlPullActors) SaveActor(Actor);
    for (AActor* Actor : LanternActors) SaveActor(Actor);
    SaveActor(ChainActor);
    SaveActor(LanternActor);
    SaveActor(FrontCamera);
    SaveActor(PeekCamera);
    SaveActor(CabinCamera);
    SaveActor(LoafCamera);
    CameraHeight = LoafShotSeconds = 0.f;
    bPlayedStart = bPlayedPull = bPlayedLatch = false;
    TimelineSeconds = PhaseSeconds = 0.f;
}

bool ACatrunElevatorTransition::TryBegin(APawn* Pawn)
{
    if (State != ECatrunElevatorState::Waiting || !IsValid(CatMark)
        || (bArrivalSide ? !bArrivalExpected : (!Pawn || !ContainsCenter(CabinVolume, *Pawn) || !ContainsCenter(EntryVolume, *Pawn))))
        return false;
    auto* Character = Cast<ACharacter>(Pawn);
    auto* PC = Character ? Cast<APlayerController>(Character->GetController()) : nullptr;
    if (!PC) return false;
    const auto Reject = [this](const FString& Reason)
    {
        if (!bArrivalSide || LastArrivalRejection != Reason)
            UE_LOG(LogCatrunElevator, Warning, TEXT("Elevator could not start: %s"), *Reason);
        if (bArrivalSide) LastArrivalRejection = Reason;
        return false;
    };
    if (!IsUsableCamera(CabinCamera) || (!bArrivalSide && (!IsUsableCamera(FrontCamera) || !IsUsableCamera(PeekCamera))))
        return Reject(TEXT("Missing or invalid cinematic camera"));
    if (!ValidateClips(*Character)) return Reject(TEXT("The ordered animation clips do not match the possessed cat skeleton"));
    FText Failure;
    // The stage-start black from UCatrunRestartSubsystem is not another presentation owner; this arrival takes it over
    // in the first frame so the gameplay camera is never shown and input is never released in between.
    auto* CameraManager = PC->PlayerCameraManager.Get();
    const bool bTakesOverStartFade = bArrivalSide && CameraManager && CameraManager->bEnableFading;
    if (bTakesOverStartFade) CameraManager->bEnableFading = false;
    if (!ExitTransition->AcquireExitLease(Character, Failure))
    {
        if (bTakesOverStartFade) CameraManager->bEnableFading = true;
        return Reject(Failure.ToString());
    }
    if (!ExitTransition->ValidateExitMotion(Character->GetActorLocation(), CatMark->GetActorLocation(), true, Failure))
    {
        ExitTransition->ReleaseExitLease(false);
        if (bTakesOverStartFade) CameraManager->bEnableFading = true;
        return Reject(FString::Printf(TEXT("Cat mark is inaccessible: %s"), *Failure.ToString()));
    }
    SavePresentation(*Character, *PC);
    WearCinematicMesh(*Character);
    // Baked root travel carries the pose far from the component: fixed bounds would be occlusion-culled behind the platform.
    SavedBoundsScale = Character->GetMesh()->BoundsScale;
    Character->GetMesh()->SetBoundsScale(FMath::Max(8.f, SavedBoundsScale));
    if (bUseLocalElevatorLighting) SetLocalLighting(Character->GetMesh());
    UE_LOG(LogCatrunElevator, Log, TEXT("Elevator %s lease acquired"), bArrivalSide ? TEXT("arrival") : TEXT("departure"));
    State = ECatrunElevatorState::Aligning;
    AddLetterbox();
    HideMinimap(PC);
    if (bArrivalSide) SetFade(1.f);
    else
    {
        UpdateCabinIsolation(Character, PC, true);
        ExitTransition->RememberOwnedViewTarget(FrontCamera);
        ActiveCamera = FrontCamera.Get();
        PC->SetViewTargetWithBlend(FrontCamera, DepartureAlignSeconds, VTBlend_Cubic, 0.f, true);
    }
    return true;
}

void ACatrunElevatorTransition::UpdateAlignment(float DeltaSeconds)
{
    if (!IsValid(CatMark)) { CancelTransition(); return; }
    PhaseSeconds += DeltaSeconds;
    const float Duration = bArrivalSide ? AlignSeconds : DepartureAlignSeconds;
    const float Alpha = FMath::SmoothStep(0.f, 1.f, FMath::Clamp(PhaseSeconds / Duration, 0.f, 1.f));
    auto* Pawn = Cat.Get();
    FHitResult Hit;
    Pawn->SetActorLocation(FMath::Lerp(AlignStart, CatMark->GetActorLocation(), Alpha), true, &Hit);
    if (Hit.bBlockingHit) { CancelTransition(); return; }
    Pawn->SetActorRotation(FQuat::Slerp(AlignStartRotation, CatMark->GetActorQuat(), Alpha));
    if (PhaseSeconds < Duration) return;
    if (!bArrivalSide)
    {
        const auto* PC = Controller.Get();
        if (!PC || !PC->PlayerCameraManager || PC->GetViewTarget() != FrontCamera)
        {
            CancelTransition();
            return;
        }
        // The camera manager updates after this actor. Do not start the jump one frame before it settles.
        if (PC->PlayerCameraManager->PendingViewTarget.Target)
        {
            if (PhaseSeconds > Duration + 1.f) CancelTransition();
            return;
        }
    }
    SceneMeshWorld = Pawn->GetMesh()->GetComponentTransform();
    PhaseSeconds = 0.f;
    StartClip(0);
    State = bArrivalSide ? ECatrunElevatorState::Arrival : ECatrunElevatorState::Departure;
    // The gameplay roof is removed while walking inside. Crafted shots see the real roof.
    UpdateOccluders(false, false);
    if (bArrivalSide) ApplyCabinMotion(-ArrivalApproachDistance, 0.f, 0.f, 0.f, true, 0.f);
    if (bArrivalSide) CutTo(CabinCamera);
}

void ACatrunElevatorTransition::StartClip(int32 Index)
{
    const auto& Clips = bArrivalSide ? ArrivalClips : DepartureClips;
    if (Clips.IsValidIndex(Index) && IsValid(Clips[Index])) StartClipAsset(*Clips[Index], Index);
}

void ACatrunElevatorTransition::StartClipAsset(UAnimSequence& Clip, int32 Index)
{
    auto* Pawn = Cat.Get();
    if (!Pawn) return;
    ActiveClipIndex = Index;
    ActiveClip = &Clip;
    ClipSeconds = 0.f;
    auto* Mesh = Pawn->GetMesh();
    Mesh->PlayAnimation(ActiveClip, false);
    if (auto* Single = Mesh->GetSingleNodeInstance())
    {
        // The baked root stays in the evaluated pose. The pawn never performs a second jump.
        Single->SetRootMotionMode(ERootMotionMode::NoRootMotionExtraction);
        Single->SetPlaying(false);
        Single->SetPosition(0.f, false);
    }
    bOwnPlayback = true;
}

void ACatrunElevatorTransition::SampleClip(float Position)
{
    auto* Single = Cat->GetMesh()->GetSingleNodeInstance();
    if (!Single || Single->GetCurrentAsset() != ActiveClip) { CancelTransition(); return; }
    Single->SetPosition(FMath::Clamp(Position, 0.f, ActiveClip->GetPlayLength()), false);
}

void ACatrunElevatorTransition::CutTo(AActor* Camera)
{
    auto* PC = Controller.Get();
    if (!PC || !IsUsableCamera(Camera) || Camera == ActiveCamera.Get()) return;
    ExitTransition->RememberOwnedViewTarget(Camera);
    PC->SetViewTarget(Camera);
    // A hard cut: without the flag the first frame smears motion blur across the two shots.
    if (PC->PlayerCameraManager) PC->PlayerCameraManager->SetGameCameraCutThisFrame();
    ActiveCamera = Camera;
    UpdateShotLights();
}

void ACatrunElevatorTransition::UpdateShotLights()
{
    const AActor* Camera = ActiveCamera.Get();
    const bool bPeek = Camera && Camera == PeekCamera;
    const bool bLoaf = Camera && (Camera == LoafCamera || Camera == CabinCamera);
    for (AActor* Light : PeekLights) if (IsValid(Light)) Light->SetActorHiddenInGame(!bPeek);
    for (AActor* Light : LoafLights) if (IsValid(Light)) Light->SetActorHiddenInGame(!bLoaf);
}

void ACatrunElevatorTransition::SetAscentPresentation(bool bAscending)
{
    if (!bAscending)
    {
        for (const auto& Toggled : AscentToggledActors)
            if (AActor* Actor = Toggled.Get()) Actor->SetActorHiddenInGame(!Actor->IsHidden());
        AscentToggledActors.Reset();
        return;
    }
    if (!AscentToggledActors.IsEmpty()) return;
    const auto Toggle = [this](const TArray<TObjectPtr<AActor>>& Actors, bool bHide)
    {
        for (AActor* Actor : Actors)
        {
            if (!IsValid(Actor) || Actor->IsHidden() == bHide) continue;
            Actor->SetActorHiddenInGame(bHide);
            AscentToggledActors.Add(Actor);
        }
    };
    Toggle(AscentHiddenActors, true);
    Toggle(AscentShownActors, false);
}

void ACatrunElevatorTransition::SetFade(float Alpha)
{
    auto* PC = Controller.Get();
    if (!PC || !PC->PlayerCameraManager) return;
    if (Alpha > 0.f)
    {
        PC->PlayerCameraManager->SetManualCameraFade(FMath::Clamp(Alpha, 0.f, 1.f), FLinearColor::Black, false);
        bOwnFade = true;
    }
    else if (bOwnFade)
    {
        PC->PlayerCameraManager->StopCameraFade();
        bOwnFade = false;
    }
}

void ACatrunElevatorTransition::AddLetterbox()
{
    auto* Viewport = GetWorld()->GetGameViewport();
    if (!Viewport || Letterbox.IsValid()) return;
    LetterboxFraction = 0.f;
    const TWeakObjectPtr<ACatrunElevatorTransition> Weak(this);
    Letterbox = SNew(SElevatorLetterbox)
        .Visibility(EVisibility::HitTestInvisible)
        .Fraction_Lambda([Weak] { return Weak.IsValid() ? Weak->LetterboxFraction : 0.f; });
    Letterbox->ForceVolatile(true);
    LetterboxViewport = Viewport;
    Viewport->AddViewportWidgetContent(Letterbox.ToSharedRef(), 1000);
}

void ACatrunElevatorTransition::RemoveLetterbox()
{
    if (Letterbox.IsValid() && LetterboxViewport.IsValid())
        LetterboxViewport->RemoveViewportWidgetContent(Letterbox.ToSharedRef());
    Letterbox.Reset();
    LetterboxViewport.Reset();
    LetterboxFraction = 0.f;
}

void ACatrunElevatorTransition::HideMinimap(APlayerController* PC, float DeltaSeconds)
{
    if (MinimapController.Get() != PC) RestoreMinimap();
    if (!PC) return;
    MinimapController = PC;
    for (auto It = MinimapVisibility.CreateIterator(); It; ++It)
    {
        auto* Widget = It.Key().Get();
        if (!Widget) { It.RemoveCurrent(); continue; }
        // Tab changes the map's size/opacity; it cannot reopen a collapsed zone-owned widget.
        if (Widget->IsVisible()) Widget->SetVisibility(ESlateVisibility::Collapsed);
    }
    // Also discover a replacement or a Stage3 widget created after the first suppression pass.
    MinimapRetrySeconds -= DeltaSeconds;
    if (MinimapRetrySeconds > 0.f) return;
    MinimapRetrySeconds = .1f;
    TArray<UUserWidget*> Widgets;
    UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, UCatrunMinimapWidget::StaticClass(), true);
    for (auto* Widget : Widgets)
    {
        if (Widget->GetOwningPlayer() != PC || !Widget->IsVisible() || MinimapVisibility.Contains(Widget)) continue;
        MinimapVisibility.Add(Widget, Widget->GetVisibility());
        Widget->SetVisibility(ESlateVisibility::Collapsed);
    }
}

void ACatrunElevatorTransition::RestoreMinimap()
{
    for (const auto& Entry : MinimapVisibility)
        if (auto* Widget = Entry.Key.Get(); Widget && Widget->GetVisibility() == ESlateVisibility::Collapsed)
            Widget->SetVisibility(Entry.Value);
    MinimapVisibility.Reset();
    MinimapController.Reset();
    MinimapRetrySeconds = 0.f;
}

void ACatrunElevatorTransition::PositionArrivalTitle(APlayerController* PC, float DeltaSeconds)
{
    if (!bArrivalExpected || TitlePlacementTimeLeft <= 0.f) return;
    TitlePlacementTimeLeft -= DeltaSeconds;
    TitlePlacementRetrySeconds -= DeltaSeconds;
    if (!PC || TitlePlacementRetrySeconds > 0.f) return;
    TitlePlacementRetrySeconds = .1f;
    auto* TitleClass = FindObject<UClass>(nullptr, TEXT("/Game/UI/Continue/WBP_StageTitle.WBP_StageTitle_C"));
    if (!TitleClass) return;
    TArray<UUserWidget*> Widgets;
    UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, TitleClass, true);
    for (UUserWidget* Widget : Widgets)
    {
        if (Widget->GetOwningPlayer() != PC || Widget->GetClass() != TitleClass) continue;
        Widget->SetRenderTranslation(Widget->GetRenderTransform().Translation + FVector2D(0., 120.));
        TitlePlacementTimeLeft = 0.f;
        return;
    }
}

void ACatrunElevatorTransition::UpdateJumpCamera(float Position)
{
    if (!IsValid(FrontCamera) || ActiveCamera.Get() != FrontCamera) return;
    const FTransform* Rest = RestTransforms.Find(FrontCamera.Get());
    if (!Rest) return;
    float Track = 0.f;
    switch (ActiveClipIndex)
    {
    case 0: Track = -.21f * FMath::SmoothStep(.3f, ActiveClip->GetPlayLength(), Position); break;
    case 1: Track = FMath::Lerp(-.21f, 1.f, FMath::SmoothStep(.18f, .79f, Position)); break;
    case 2: Track = FMath::Lerp(1.f, .78f, FMath::SmoothStep(.12f, .88f, Position)); break;
    case 3: Track = .78f * (1.f - FMath::SmoothStep(0.f, .7f, Position)); break;
    default: return;
    }
    FRotator Rotation = Rest->Rotator();
    Rotation.Pitch += 5.f * Track;
    FrontCamera->SetActorLocationAndRotation(Rest->GetLocation() + FVector::UpVector * (48.f * Track)
        + Rest->GetRotation().GetForwardVector() * (32.f * Track), Rotation);
}

void ACatrunElevatorTransition::UpdatePeekCamera(float DeltaSeconds)
{
    auto* Pawn = Cat.Get();
    if (!Pawn || !IsUsableCamera(PeekCamera)) return;
    auto* Mesh = Pawn->GetMesh();
    // Evaluate the just-sampled pose after cabin motion, so the lens follows this frame's actual face.
    Mesh->RefreshBoneTransforms();
    static const FName LeftEye(TEXT("lid_upper_l_00"));
    static const FName RightEye(TEXT("lid_upper_r_00"));
    static const FName Head(TEXT("head"));
    FVector Target;
    if (Mesh->GetBoneIndex(LeftEye) != INDEX_NONE && Mesh->GetBoneIndex(RightEye) != INDEX_NONE)
        Target = .5 * (Mesh->GetBoneLocation(LeftEye) + Mesh->GetBoneLocation(RightEye));
    else
    {
        const FVector Forward = IsValid(CatMark) ? CatMark->GetActorForwardVector() : Pawn->GetActorForwardVector();
        Target = (Mesh->GetBoneIndex(Head) != INDEX_NONE ? Mesh->GetBoneLocation(Head) : Mesh->GetComponentLocation())
            + Forward * 8. + FVector::UpVector * 2.;
    }
    // Keep the platform edge in frame: the face sits above centre and climbs a little as the cabin leaves.
    Target -= FVector::UpVector * 7.;
    const FVector Direction = Target - PeekCamera->GetActorLocation();
    if (Direction.IsNearlyZero() || Direction.ContainsNaN()) return;
    FRotator Desired = Direction.Rotation();
    if (const auto* Rest = RestTransforms.Find(PeekCamera.Get())) Desired.Roll = Rest->Rotator().Roll;
    // Aim before the first cut; subsequent frames keep the stationary lens and smoothly track rotation only.
    const FRotator Rotation = ActiveCamera.Get() == PeekCamera
        ? FMath::RInterpTo(PeekCamera->GetActorRotation(), Desired, DeltaSeconds, 2.2f) : Desired;
    PeekCamera->SetActorRotation(Rotation);
}

void ACatrunElevatorTransition::UpdateLoafCamera(float DeltaSeconds)
{
    auto* Pawn = Cat.Get();
    const FTransform* Rest = RestTransforms.Find(LoafCamera.Get());
    if (!Pawn || !Rest || !IsUsableCamera(LoafCamera)) return;
    auto* Mesh = Pawn->GetMesh();
    Mesh->RefreshBoneTransforms();
    static const FName Spine(TEXT("spine"));
    // Work in cabin space: the lens never inherits the sway, so the timber visibly rocks around the cat.
    FVector Target = (Mesh->GetBoneIndex(Spine) != INDEX_NONE ? Mesh->GetBoneLocation(Spine) : Mesh->GetComponentLocation())
        - FVector::UpVector * CameraHeight;
    if (LoafShotSeconds <= 0.f) LoafAim = Target;
    LoafAim = FMath::VInterpTo(LoafAim, Target, DeltaSeconds, 2.6f);
    LoafShotSeconds += DeltaSeconds;
    const float Push = FMath::SmoothStep(.8f, 7.6f, LoafShotSeconds);
    const FVector Location = Rest->GetLocation() + Rest->GetRotation().GetForwardVector() * (90.f * Push);
    const FVector RestAim = Rest->GetLocation() + Rest->GetRotation().GetForwardVector() * FVector::Distance(Rest->GetLocation(), LoafAim);
    const FVector Direction = FMath::Lerp(RestAim, LoafAim, .7) - Location;
    if (Direction.IsNearlyZero() || Direction.ContainsNaN()) return;
    LoafCamera->SetActorLocationAndRotation(Location + FVector::UpVector * CameraHeight, Direction.Rotation());
}

void ACatrunElevatorTransition::ApplyCabinMotion(float Height, float Sway, float LanternSwing, float ChainPull, bool bMoveCat, float CameraRise)
{
    const FQuat CabinRotation(FVector::ForwardVector, FMath::DegreesToRadians(Sway));
    const FQuat LanternRotation(FVector::ForwardVector, FMath::DegreesToRadians(LanternSwing));
    const FVector Rise(0., 0., Height);
    const auto RigidMotion = [this, &CabinRotation, &Rise](FTransform Transform)
    {
        Transform.SetLocation(MotionPivot + CabinRotation.RotateVector(Transform.GetLocation() - MotionPivot) + Rise);
        Transform.SetRotation(CabinRotation * Transform.GetRotation());
        return Transform;
    };
    for (const auto& Item : RestTransforms)
    {
        AActor* Actor = Item.Key.Get();
        if (!Actor || (!bArrivalSide && Actor == PeekCamera)) continue;
        // An authored attachment already follows a moving ancestor.
        bool bHasMovingParent = false;
        for (AActor* Parent = Actor->GetAttachParentActor(); Parent; Parent = Parent->GetAttachParentActor())
            if (RestTransforms.Contains(Parent)) { bHasMovingParent = true; break; }
        if (bHasMovingParent) continue;
        FTransform Transform = Item.Value;
        if (Actor == FrontCamera || Actor == CabinCamera || Actor == LoafCamera)
        {
            // Lenses follow the height only. Sway and jolts stay visible as the cabin moving in frame.
            Transform.AddToTranslation(FVector(0., 0., CameraRise));
            Actor->SetActorTransform(Transform, false, nullptr, ETeleportType::TeleportPhysics);
            continue;
        }
        if (Actor == LanternActor || LanternActors.Contains(Actor))
        {
            Transform.SetLocation(LanternPivot + LanternRotation.RotateVector(Transform.GetLocation() - LanternPivot));
            Transform.SetRotation(LanternRotation * Transform.GetRotation());
        }
        if (Actor == ChainActor || ControlPullActors.Contains(Actor)) Transform.AddToTranslation(FVector(0., 0., -ChainPull));
        Actor->SetActorTransform(RigidMotion(Transform), false, nullptr, ETeleportType::TeleportPhysics);
    }
    if (bMoveCat)
        if (auto* Pawn = Cat.Get()) Pawn->GetMesh()->SetWorldTransform(RigidMotion(SceneMeshWorld), false, nullptr, ETeleportType::TeleportPhysics);
}
void ACatrunElevatorTransition::UpdateDeparture(float DeltaSeconds)
{
    float RemainingSeconds = FMath::Max(0.f, DeltaSeconds);
    while (RemainingSeconds > 0.f)
    {
        const float ClipLength = ActiveClip->GetPlayLength();
        // The last clip is the looping loaf: it lasts as long as the ride, not as long as the asset.
        const float Duration = ActiveClipIndex == RideClipIndex ? RideSeconds : ClipLength;
        const float SecondsToBoundary = FMath::Max(0.f, Duration - ClipSeconds);
        if (RemainingSeconds < SecondsToBoundary)
        {
            ClipSeconds += RemainingSeconds;
            break;
        }
        ClipSeconds = Duration;
        RemainingSeconds -= SecondsToBoundary;
        if (ActiveClipIndex == DepartureClips.Num() - 1)
        {
            SampleClip(FMath::Fmod(Duration, ClipLength));
            if (State != ECatrunElevatorState::Departure) return;
            State = ECatrunElevatorState::Blackout;
            PhaseSeconds = 0.f;
            SetFade(1.f);
            return;
        }
        StartClip(ActiveClipIndex + 1);
    }
    const float SampleTime = ClipSeconds;
    SampleClip(ActiveClipIndex == RideClipIndex ? FMath::Fmod(SampleTime, ActiveClip->GetPlayLength()) : SampleTime);
    if (State != ECatrunElevatorState::Departure) return;

    if (ActiveClipIndex < 4)
    {
        const float Pull = ActiveClipIndex == 2 ? 18.f * FMath::SmoothStep(4.f / 30.f, 23.f / 30.f, SampleTime)
            : ActiveClipIndex == 3 ? 18.f * (1.f - FMath::SmoothStep(0.f, .22f, SampleTime)) : 0.f;
        if (!bPlayedPull && Pull > 0.f)
        {
            bPlayedPull = true;
            if (PullSound) UGameplayStatics::PlaySoundAtLocation(this, PullSound, ChainActor ? ChainActor->GetActorLocation() : MotionPivot);
        }
        ApplyCabinMotion(0.f, 0.f, 0.f, Pull, true);
        UpdateJumpCamera(SampleTime);
        return;
    }

    const float StartupLength = DepartureClips[4]->GetPlayLength();
    const float PeekLength = DepartureClips[PeekClipIndex]->GetPlayLength();
    float MovingTime = SampleTime - StartImpact;
    if (ActiveClipIndex >= PeekClipIndex) MovingTime += StartupLength;
    if (ActiveClipIndex >= RideClipIndex) MovingTime += PeekLength;
    if (MovingTime >= 0.f && !bPlayedStart)
    {
        bPlayedStart = true;
        if (StartSound) UGameplayStatics::PlaySoundAtLocation(this, StartSound, MotionPivot);
    }
    MovingTime = FMath::Max(0.f, MovingTime);
    // Soft start, then a steady climb that is still moving when the picture goes black.
    const float RiseTime = StartupLength + PeekLength + RideSeconds - StartImpact;
    const float RiseFraction = (MovingTime < RiseEaseSeconds ? FMath::Square(MovingTime) / (2.f * RiseEaseSeconds)
        : MovingTime - .5f * RiseEaseSeconds) / FMath::Max(.1f, RiseTime - .5f * RiseEaseSeconds);
    const float Jolt = 2.2f * FMath::Sin(MovingTime * 15.f) * FMath::Exp(-2.6f * MovingTime);
    const float Sway = Jolt + FMath::SmoothStep(0.f, .85f, MovingTime)
        * (.75f * FMath::Sin(MovingTime * 2.f) + .25f * FMath::Sin(MovingTime * 5.3f + 1.1f));
    const float Swing = 5.5f * FMath::Sin(MovingTime * 3.5f) * FMath::SmoothStep(0.f, .65f, MovingTime);
    // Rail joints: a small knock every few seconds.
    const float KnockAge = FMath::Fmod(MovingTime + .6f, 2.7f);
    const float Knock = MovingTime > 2.f ? -.55f * FMath::Cos(26.f * KnockAge) * FMath::Exp(-7.f * KnockAge) : 0.f;
    const float Rise = DepartureRiseDistance * FMath::Min(1.f, RiseFraction);
    if (ActiveClipIndex >= PeekClipIndex)
    {
        SetAscentPresentation(true);
        const bool bPeek = ActiveClipIndex == PeekClipIndex && SampleTime >= PeekShotStartSeconds && SampleTime < PeekShotEndSeconds;
        AActor* Shot = ActiveClipIndex == RideClipIndex ? CabinCamera.Get() : bPeek ? PeekCamera.Get()
            : SampleTime >= PeekShotEndSeconds && IsUsableCamera(LoafCamera) ? LoafCamera.Get() : FrontCamera.Get();
        const bool bCut = Shot != ActiveCamera.Get();
        // The launch lens lets the cabin lift off first; the last one lets it leave through the top of the frame.
        if (bCut && Shot != PeekCamera) CameraHeight = Rise;
        if (Shot == CabinCamera) CameraHeight += FMath::Max(0.f, Rise - CameraHeight)
            * (1.f - FMath::Exp(-DeltaSeconds * FMath::Lerp(6.f, .35f, FMath::SmoothStep(.5f, 1.8f, SampleTime))));
        else if (Shot == LoafCamera) CameraHeight = Rise;
        else if (Shot == FrontCamera) CameraHeight = FMath::FInterpTo(CameraHeight, Rise, DeltaSeconds, 1.f);
        ApplyCabinMotion(Rise + Knock, Sway, Swing, 0.f, true, CameraHeight);
        if (Shot == FrontCamera)
        {
            // Walking to the edge brings the cat closer and lower in frame; keep its paws above the letterbox.
            FRotator Tilt = FrontCamera->GetActorRotation();
            Tilt.Pitch -= 4.f * FMath::SmoothStep(.35f, PeekShotStartSeconds, SampleTime);
            FrontCamera->SetActorRotation(Tilt);
        }
        if (bPeek) UpdatePeekCamera(DeltaSeconds);
        else if (Shot == LoafCamera && Shot != FrontCamera) UpdateLoafCamera(DeltaSeconds);
        CutTo(Shot);
        if (ActiveClipIndex == RideClipIndex)
            SetFade(FMath::SmoothStep(.58f * RideSeconds, .98f * RideSeconds, SampleTime));
        return;
    }
    CameraHeight = FMath::FInterpTo(CameraHeight, Rise, DeltaSeconds, 1.f);
    ApplyCabinMotion(Rise + Knock, Sway, Swing, 0.f, true, CameraHeight);
}

void ACatrunElevatorTransition::UpdateArrival(float DeltaSeconds)
{
    PhaseSeconds += DeltaSeconds;
    if (PhaseSeconds < ApproachSeconds + LoafReadSeconds)
    {
        const float Rise = FMath::SmoothStep(0.f, ApproachSeconds, PhaseSeconds);
        const float Sway = .8f * FMath::Sin(PI * Rise) * (1.f - Rise);
        // The lens waits at the dock; riding up with the cabin it passed through the floor slab.
        ApplyCabinMotion(-ArrivalApproachDistance * (1.f - Rise), Sway, Sway * 4.f, 0.f, true, 0.f);
        SampleClip(FMath::Fmod(PhaseSeconds, ActiveClip->GetPlayLength()));
        if (State == ECatrunElevatorState::Arrival) SetFade(1.f - FMath::SmoothStep(.12f, .7f, PhaseSeconds));
        return;
    }
    if (ActiveClipIndex == 0) StartClip(1);
    // The delivered rise includes its own loaf pre-roll. C08 already held the loaf after docking.
    const float Position = LatchClipLeadIn + PhaseSeconds - ApproachSeconds - LoafReadSeconds;
    SampleClip(Position);
    if (State != ECatrunElevatorState::Arrival) return;
    if (!bPlayedLatch && Position >= LatchClipImpact)
    {
        bPlayedLatch = true;
        if (DockLatchSound) UGameplayStatics::PlaySoundAtLocation(this, DockLatchSound, MotionPivot);
    }
    const float LatchAge = Position - LatchClipImpact;
    if (LatchAge >= 0.f && LatchAge < .55f)
    {
        const float Damping = FMath::Exp(-7.5f * LatchAge) * (1.f - FMath::SmoothStep(.35f, .55f, LatchAge));
        const float Bounce = -1.5f * FMath::Cos(26.f * LatchAge) * Damping;
        const float Roll = 2.f * FMath::Sin(27.f * LatchAge + PI * .25f) * Damping;
        const float LanternSwing = 4.f * FMath::Sin(18.f * LatchAge) * Damping;
        ApplyCabinMotion(Bounce, Roll, LanternSwing, 0.f, true, 0.f);
    }
    else if (bPlayedLatch)
        ApplyCabinMotion(0.f, 0.f, 0.f, 0.f, true);
    if (Position >= ActiveClip->GetPlayLength()) BeginArrivalWalk();
}

void ACatrunElevatorTransition::FinishDeparture()
{
    SetFade(1.f);
    State = ECatrunElevatorState::Travelling;
    if (!ExitTransition->CommitExitTravel())
    {
        if (State == ECatrunElevatorState::Travelling) CancelTransition();
    }
    else UE_LOG(LogCatrunElevator, Log, TEXT("Elevator departure requested Stage3"));
}

bool ACatrunElevatorTransition::SetCatOnMark(AActor& Mark)
{
    auto* Pawn = Cat.Get();
    FText Failure;
    if (!Pawn || !ExitTransition->ValidateExitMotion(Pawn->GetActorLocation(), Mark.GetActorLocation(), true, Failure)) return false;
    FHitResult Hit;
    Pawn->SetActorLocation(Mark.GetActorLocation(), true, &Hit);
    if (Hit.bBlockingHit) return false;
    Pawn->SetActorRotation(Mark.GetActorQuat());
    return true;
}

void ACatrunElevatorTransition::BeginArrivalWalk()
{
    auto* Pawn = Cat.Get();
    ApplyCabinMotion(0.f, 0.f, 0.f, 0.f, false);
    Pawn->GetMesh()->SetRelativeTransform(OriginalMeshRelative);
    FText Failure;
    if (!IsValid(ArrivalReleaseMark) ||
        !ExitTransition->ValidateExitMotion(Pawn->GetActorLocation(), ArrivalReleaseMark->GetActorLocation(), true, Failure))
    {
        UE_LOG(LogCatrunElevator, Warning, TEXT("Arrival walk path unavailable: %s"), *Failure.ToString());
        BeginArrivalLook();
        return;
    }

    WalkStart = Pawn->GetActorTransform();
    WalkDestination = ArrivalReleaseMark->GetActorTransform();
    const FVector Path = WalkDestination.GetLocation() - WalkStart.GetLocation();
    const float Speed = FMath::Clamp(FMath::IsFinite(ArrivalWalkSpeed) ? ArrivalWalkSpeed : 90.f, 5.f, 200.f);
    WalkDuration = FMath::Max(.3f, static_cast<float>(Path.Size2D()) / Speed);
    PhaseSeconds = 0.f;
    State = ECatrunElevatorState::ArrivalWalk;
    // Stage3 lights must reach the cat outside, or it walks on a bright floor as a black cut-out.
    if (LitMesh.IsValid()) LitMesh->SetLightingChannels(true, true, false);
    StartCabinWeight(Pawn);
    if (MatchesCatSkeleton(ArrivalExitWalkClip, *Pawn)) StartClipAsset(*ArrivalExitWalkClip, ArrivalWalkClipIndex);
    if (IsUsableCamera(ArrivalExitCamera))
    {
        TrackedArrivalExitCamera = ArrivalExitCamera.Get();
        bReturnPath = true;
        ArrivalExitCameraStart = ArrivalExitCamera->GetActorTransform();
        CutTo(ArrivalExitCamera);
    }
}

void ACatrunElevatorTransition::UpdateArrivalWalk(float DeltaSeconds)
{
    auto* Pawn = Cat.Get();
    PhaseSeconds += DeltaSeconds;
    const float Alpha = FMath::Clamp(PhaseSeconds / WalkDuration, 0.f, 1.f);
    const FVector Path = WalkDestination.GetLocation() - WalkStart.GetLocation();
    const FVector Desired = WalkStart.GetLocation() + Path * Alpha;
    const float StepHeight = FMath::Max(0.f, Pawn->GetCharacterMovement()->MaxStepHeight);
    FCollisionQueryParams FloorParams(SCENE_QUERY_STAT(ElevatorArrivalFloor), false, Pawn);
    FloorParams.AddIgnoredActor(this);
    FHitResult Support;
    FVector Next;
    FText Failure;
    if (!CatrunGround::FindSupport(*Pawn->GetCapsuleComponent(), Desired, StepHeight, StepHeight + 3.f,
            FloorParams, Support, Next)
        || !ExitTransition->ValidateExitMotion(Pawn->GetActorLocation(), Next, false, Failure))
    {
        UE_LOG(LogCatrunElevator, Warning, TEXT("Arrival walk interrupted: %s"), *Failure.ToString());
        BeginArrivalLook();
        return;
    }
    FHitResult Hit;
    Pawn->SetActorLocation(Next, true, &Hit);
    if (auto* Camera = TrackedArrivalExitCamera.Get(); Camera && Camera == ActiveCamera.Get())
    {
        FVector HorizontalTravel = Pawn->GetActorLocation() - WalkStart.GetLocation();
        HorizontalTravel.Z = 0.f;
        Camera->SetActorLocation(ArrivalExitCameraStart.GetLocation() + HorizontalTravel);
    }
    if (Hit.bBlockingHit) { BeginArrivalLook(); return; }
    const FQuat Forward = Path.IsNearlyZero() ? WalkStart.GetRotation() : FRotator(0.f, Path.Rotation().Yaw, 0.f).Quaternion();
    const FQuat Facing = FQuat::Slerp(WalkStart.GetRotation(), Forward, FMath::SmoothStep(0.f, .15f, Alpha));
    Pawn->SetActorRotation(FQuat::Slerp(Facing, WalkDestination.GetRotation(), FMath::SmoothStep(.85f, 1.f, Alpha)));
    if (ActiveClipIndex == ArrivalWalkClipIndex)
    {
        const float Rate = FMath::Clamp(FMath::IsFinite(ArrivalWalkClipPlayRate) ? ArrivalWalkClipPlayRate : 1.f, .1f, 8.f);
        SampleClip(FMath::Fmod(PhaseSeconds * Rate, ActiveClip->GetPlayLength()));
    }
    if (State == ECatrunElevatorState::ArrivalWalk && Alpha >= 1.f) BeginArrivalLook();
}

void ACatrunElevatorTransition::BeginArrivalLook()
{
    auto* Pawn = Cat.Get();
    LookBaseRotation = Pawn->GetActorQuat();
    PhaseSeconds = 0.f;
    State = ECatrunElevatorState::ArrivalLook;
    if (MatchesCatSkeleton(ArrivalLookAroundClip, *Pawn))
    {
        StartClipAsset(*ArrivalLookAroundClip, ArrivalLookClipIndex);
        LookClipStart = FMath::Clamp(FMath::IsFinite(ArrivalLookClipStartSeconds) ? ArrivalLookClipStartSeconds : 0.f,
            0.f, FMath::Max(0.f, ActiveClip->GetPlayLength() - .15f));
        SampleClip(LookClipStart);
    }
    else if (ActiveClipIndex == ArrivalWalkClipIndex)
    {
        StartClip(1);
        SampleClip(ActiveClip->GetPlayLength());
    }
}

void ACatrunElevatorTransition::UpdateArrivalLook(float DeltaSeconds)
{
    PhaseSeconds += DeltaSeconds;
    if (ActiveClipIndex == ArrivalLookClipIndex)
    {
        const float Length = ActiveClip->GetPlayLength();
        const float Position = LookClipStart + PhaseSeconds;
        SampleClip(Position);
        if (State == ECatrunElevatorState::ArrivalLook && Position >= Length) BeginArrivalBlend();
        return;
    }
    const float Alpha = FMath::Clamp(PhaseSeconds / FallbackLookSeconds, 0.f, 1.f);
    const float Yaw = 22.f * FMath::Sin(2.f * PI * Alpha);
    Cat->SetActorRotation(FQuat(FVector::UpVector, FMath::DegreesToRadians(Yaw)) * LookBaseRotation);
    if (Alpha >= 1.f) BeginArrivalBlend();
}

void ACatrunElevatorTransition::BeginArrivalBlend()
{
    auto* PC = Controller.Get();
    AActor* View = GameplayCamera.Get();
    if (!PC || !IsUsableCamera(View) || ExitTransition->IsArrivalViewSettled(View))
    {
        FinishArrival();
        return;
    }
    State = ECatrunElevatorState::ArrivalBlend;
    PhaseSeconds = 0.f;
    if (LitMesh.IsValid()) LitMesh->SetLightingChannels(true, true, false);
    auto* Exit = TrackedArrivalExitCamera.Get();
    auto* ExitLens = Exit && Exit == ActiveCamera.Get() ? Exit->FindComponentByClass<UCameraComponent>() : nullptr;
    if (bReturnPath && ExitLens)
    {
        ReturnSeconds = FMath::Clamp(FMath::IsFinite(ArrivalCameraBlendSeconds) ? ArrivalCameraBlendSeconds : 1.f, .1f, 3.f);
        ReturnStart = Exit->GetActorTransform();
        ReturnStartFOV = ReturnExitFOV = ExitLens->FieldOfView;
        return;
    }
    bReturnPath = false;
    const float Duration = FMath::Clamp(FMath::IsFinite(ArrivalCameraBlendSeconds) ? ArrivalCameraBlendSeconds : .75f, .1f, 3.f);
    PC->SetViewTargetWithBlend(View, Duration, VTBlend_Cubic, 0.f, true);
}

void ACatrunElevatorTransition::UpdateReturnPath()
{
    auto* PC = Controller.Get();
    auto* Exit = TrackedArrivalExitCamera.Get();
    auto* Lens = Exit ? Exit->FindComponentByClass<UCameraComponent>() : nullptr;
    AActor* View = GameplayCamera.Get();
    if (!PC || !Lens || !IsUsableCamera(View) || !Cat.IsValid()) { CancelTransition(); return; }
    const float Alpha = FMath::InterpEaseInOut(0.f, 1.f, FMath::Clamp(PhaseSeconds / ReturnSeconds, 0.f, 1.f), 2.5f);
    if (Alpha >= 1.f)
    {
        bReturnPath = false;
        PC->SetViewTarget(View);
        return;
    }
    FMinimalViewInfo End;
    View->CalcCamera(0.f, End);
    // The straight path of a plain blend, but the cat keeps its place on screen instead of dropping out of frame.
    const FVector Focus = Cat->GetActorLocation();
    if (End.ProjectionMode == ECameraProjectionMode::Orthographic)
    {
        // Finish on a long lens that frames exactly what the orthographic gameplay view shows, so the hand-over does not jump.
        const FVector Forward = End.Rotation.Vector();
        const FVector Center = End.Location + Forward * ((Focus - End.Location) | Forward);
        End.FOV = 22.f;
        End.Location = Center - Forward * (End.OrthoWidth * .5f / FMath::Tan(FMath::DegreesToRadians(End.FOV * .5f)));
    }
    const auto Deviation = [&Focus](const FVector& Location, const FQuat& Rotation)
    {
        return (Focus - Location).Rotation().Quaternion().Inverse() * Rotation;
    };
    const FVector From = ReturnStart.GetLocation() - Focus;
    const FVector To = End.Location - Focus;
    FVector Direction = FMath::Lerp(From.GetSafeNormal(), To.GetSafeNormal(), Alpha);
    Direction.Z += .3f * FMath::Sin(PI * Alpha);
    const FVector Location = Focus + Direction.GetSafeNormal()
        * FMath::Exp(FMath::Lerp(FMath::Loge(FMath::Max(1.f, From.Size())), FMath::Loge(FMath::Max(1.f, To.Size())), Alpha));
    const FQuat Offset = FQuat::Slerp(Deviation(ReturnStart.GetLocation(), ReturnStart.GetRotation()),
        Deviation(End.Location, End.Rotation.Quaternion()), Alpha);
    Exit->SetActorLocationAndRotation(Location, (Focus - Location).Rotation().Quaternion() * Offset);
    Lens->SetFieldOfView(FMath::Lerp(ReturnStartFOV, End.FOV, Alpha));
}

void ACatrunElevatorTransition::UpdateArrivalBlend(float DeltaSeconds)
{
    PhaseSeconds += DeltaSeconds;
    LetterboxFraction *= 1.f - FMath::SmoothStep(0.f, .35f, PhaseSeconds);
    if (bReturnPath)
    {
        UpdateReturnPath();
        return;
    }
    if (ExitTransition->IsArrivalViewSettled(GameplayCamera.Get())) FinishArrival();
    else if (PhaseSeconds > 3.5f) CancelTransition();
}

void ACatrunElevatorTransition::FinishArrival()
{
    RestorePresentation();
    ExitTransition->ReleaseExitLease(false);
    StartCabinWeight();
    State = ECatrunElevatorState::Finished;
    if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->ReleaseElevatorArrival(*this);
    UE_LOG(LogCatrunElevator, Log, TEXT("Elevator arrival released gameplay"));
}

void ACatrunElevatorTransition::RestorePresentation()
{
    if (!CabinWeight->IsResponding()) ApplyCabinMotion(0.f, 0.f, 0.f, 0.f, false);
    CabinWeight->SetScriptedRider(nullptr);
    if (auto* Camera = TrackedArrivalExitCamera.Get())
    {
        Camera->SetActorTransform(ArrivalExitCameraStart);
        if (auto* Lens = Camera->FindComponentByClass<UCameraComponent>(); Lens && ReturnExitFOV > 0.f) Lens->SetFieldOfView(ReturnExitFOV);
    }
    ReturnExitFOV = 0.f;
    bReturnPath = false;
    TrackedArrivalExitCamera.Reset();
    if (IsValid(PeekCamera))
        if (const auto* Rest = RestTransforms.Find(PeekCamera.Get())) PeekCamera->SetActorTransform(*Rest);
    RestTransforms.Reset();
    SetAscentPresentation(false);
    ActiveCamera.Reset();
    UpdateShotLights();
    UpdateOccluders(false, false);
    RestoreCabinIsolation();
    SetFade(0.f);
    RemoveLetterbox();
    RestoreMinimap();
    if (auto* Pawn = Cat.Get())
    {
        auto* Mesh = Pawn->GetMesh();
        auto* Single = Mesh->GetSingleNodeInstance();
        Mesh->SetBoundsScale(SavedBoundsScale);
        if (bOwnPlayback)
        {
            Mesh->SetRelativeTransform(OriginalMeshRelative);
            const bool bOurClip = Single && Single->GetCurrentAsset() == ActiveClip;
            if (PlayMesh && Mesh->GetSkeletalMeshAsset() == CinematicMesh)
            {
                Mesh->Stop();
                Mesh->SetSkeletalMeshAsset(PlayMesh);
                Mesh->OverrideMaterials = PlayMaterials;
                Mesh->MarkRenderStateDirty();
            }
            if (bOurClip)
            {
                Mesh->SetAnimInstanceClass(SavedAnimClass);
                Mesh->AnimationData = SavedAnimation;
                Mesh->SetAnimationMode(SavedAnimMode, true);
                if (SavedAnimMode == EAnimationMode::AnimationSingleNode && SavedAnimation.AnimToPlay)
                {
                    Mesh->PlayAnimation(SavedAnimation.AnimToPlay, SavedAnimation.bSavedLooping);
                    Mesh->SetPosition(SavedAnimation.SavedPosition, false);
                    Mesh->SetPlayRate(SavedAnimation.SavedPlayRate);
                    if (!SavedAnimation.bSavedPlaying) Mesh->Stop();
                }
            }
        }
    }
    bOwnPlayback = false;
    PlayMesh = nullptr;
    PlayMaterials.Reset();
    SetLocalLighting(nullptr);
    ActiveClip = nullptr;
    ActiveClipIndex = INDEX_NONE;
    ActiveCamera.Reset();
    GameplayCamera.Reset();
    SavedAnimClass = nullptr;
    SavedAnimation = FSingleAnimationPlayData{};
    Cat.Reset();
    Controller.Reset();
}

void ACatrunElevatorTransition::CancelTransition()
{
    if (State == ECatrunElevatorState::Finished || (State == ECatrunElevatorState::Waiting && !ExitTransition->HasExitLease())) return;
    RestorePresentation();
    ExitTransition->ReleaseExitLease(true);
    State = bArrivalSide ? ECatrunElevatorState::Finished : ECatrunElevatorState::Waiting;
    if (bArrivalSide)
    {
        if (!IsActorBeingDestroyed()) StartCabinWeight();
        if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->ReleaseElevatorArrival(*this);
    }
    else if (!IsActorBeingDestroyed() && GetWorld() && !GetWorld()->bIsTearingDown)
    {
        auto* PC = UGameplayStatics::GetPlayerController(this, 0);
        UpdateZonePresentation(PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr, PC, 0.f);
    }
}

bool ACatrunElevatorTransition::SkipTransition()
{
    if (!ExitTransition->HasExitLease() || State == ECatrunElevatorState::Travelling || GetWorld()->IsPaused()) return false;
    if (bArrivalSide)
    {
        if (State == ECatrunElevatorState::ArrivalBlend) return false;
        bReturnPath = false;
        auto* Pawn = Cat.Get();
        if (!Pawn) { CancelTransition(); return false; }
        if (!CabinWeight->IsResponding()) ApplyCabinMotion(0.f, 0.f, 0.f, 0.f, false);
        Pawn->GetMesh()->SetRelativeTransform(OriginalMeshRelative);
        if (IsValid(ArrivalReleaseMark)) SetCatOnMark(*ArrivalReleaseMark);
        SetFade(0.f);
        BeginArrivalBlend();
    }
    else FinishDeparture();
    return bArrivalSide || State == ECatrunElevatorState::Travelling;
}

void ACatrunElevatorTransition::HandleTravelFailure(FText Reason)
{
    UE_LOG(LogCatrunElevator, Warning, TEXT("Elevator interrupted: %s"), *Reason.ToString());
    CancelTransition();
}

void ACatrunElevatorTransition::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto* PC = UGameplayStatics::GetPlayerController(this, 0);
    auto* Pawn = PC ? Cast<ACharacter>(PC->GetPawn()) : nullptr;
    if (State == ECatrunElevatorState::Waiting)
    {
        if (!bArrivalSide) { UpdateFreeWalk(Pawn, PC, DeltaSeconds); return; }
        ArrivalWaitSeconds += DeltaSeconds;
        if (TryBegin(Pawn)) return;
        if (ArrivalWaitSeconds >= 3.f)
        {
            UE_LOG(LogCatrunElevator, Warning, TEXT("Stage3 arrival could not obtain the elevator lease; gameplay released at its own spawn"));
            State = ECatrunElevatorState::Finished;
            StartCabinWeight();
            if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->ReleaseElevatorArrival(*this);
        }
        return;
    }
    if (State == ECatrunElevatorState::Finished)
    {
        if (bArrivalSide)
        {
            UpdateOccluders(false, Pawn && ContainsCenter(CabinVolume, *Pawn));
            PositionArrivalTitle(PC, DeltaSeconds);
        }
        return;
    }
    if (State == ECatrunElevatorState::Travelling) return;
    const bool bBlending = State == ECatrunElevatorState::ArrivalBlend;
    if (!ExitTransition->HasExitLease() || !Pawn || Pawn != Cat.Get() || PC != Controller.Get()
        || (bBlending ? PC->GetViewTarget() != (bReturnPath ? TrackedArrivalExitCamera.Get() : GameplayCamera.Get())
            : (ActiveCamera.IsValid() && PC->GetViewTarget() != ActiveCamera.Get())))
    {
        CancelTransition();
        return;
    }
    if (SkipKey.IsValid() && PC->WasInputKeyJustPressed(SkipKey)) { SkipTransition(); return; }
    TimelineSeconds += DeltaSeconds;
    HideMinimap(PC, DeltaSeconds);
    LetterboxFraction = MaxLetterboxFraction * FMath::SmoothStep(0.f, .3f, TimelineSeconds);
    switch (State)
    {
    case ECatrunElevatorState::Aligning: UpdateAlignment(DeltaSeconds); break;
    case ECatrunElevatorState::Departure: UpdateDeparture(DeltaSeconds); break;
    case ECatrunElevatorState::Blackout:
        PhaseSeconds += DeltaSeconds;
        if (PhaseSeconds >= BlackoutSeconds) FinishDeparture();
        break;
    case ECatrunElevatorState::Arrival: UpdateArrival(DeltaSeconds); break;
    case ECatrunElevatorState::ArrivalWalk: UpdateArrivalWalk(DeltaSeconds); break;
    case ECatrunElevatorState::ArrivalLook: UpdateArrivalLook(DeltaSeconds); break;
    case ECatrunElevatorState::ArrivalBlend: UpdateArrivalBlend(DeltaSeconds); break;
    default: break;
    }
}
