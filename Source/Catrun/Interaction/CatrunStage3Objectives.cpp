#include "CatrunStage3Objectives.h"
#include "CatrunStatuePuzzle.h"
#include "CatrunBasketInteractionComponent.h"
#include "CatrunPuzzleSuspension.h"
#include "Components/PrimitiveComponent.h"
#include "Components/CapsuleComponent.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Settings/CatrunInputBindings.h"
#include "Sound/CatrunNotice.h"
#include "Sound/SoundGridManager.h"

ACatrunStage3Objectives::ACatrunStage3Objectives()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}
void ACatrunStage3Objectives::BeginPlay()
{
	Super::BeginPlay();
	for (auto& Device : Devices) { Device.bReleased = false; UpdateChain(Device); }
	if (FinalLeafLeft) LeftStart = FinalLeafLeft->GetActorLocation();
	if (FinalLeafRight) RightStart = FinalLeafRight->GetActorLocation();
	if (Puzzle) for (auto& Link : Puzzle->Links)
		if (Link.PuzzleId == LockedPuzzleId) Link.bExternalGateUnlocked = false;
}
bool ACatrunStage3Objectives::AllReleased() const
{
	return Devices.Num() == 3 && Devices.ContainsByPredicate([](const auto& D) { return !D.bReleased; }) == false;
}
bool ACatrunStage3Objectives::GameplayAvailable(APawn* Cat) const
{
	if (!Cat || Cat != UGameplayStatics::GetPlayerPawn(this,0) || !GetWorld() || GetWorld()->IsPaused()
		|| UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	const auto* PC = Cast<APlayerController>(Cat->GetController());
	if (!PC || PC->IsMoveInputIgnored()) return false;
	if (const auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	if (const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>(); Actions && (Actions->Busy || Actions->IsHidden)) return false;
	const auto* Character = Cast<ACharacter>(Cat);
	return Character && Character->GetCharacterMovement()->IsMovingOnGround();
}
bool ACatrunStage3Objectives::CanRelease(int32 Index, APawn* Cat) const
{
	if (!Devices.IsValidIndex(Index) || !GameplayAvailable(Cat)) return false;
	const auto& D = Devices[Index];
	if (D.bReleased || !IsValid(D.Housing) || !IsValid(D.Ring)) return false;
	const FVector Target = D.Ring->GetActorLocation();
	// Imported FBX preserves X/Z and converts Blender Y to -Y. The public face is local +Y.
	if (D.Housing->GetActorTransform().InverseTransformPosition(Cat->GetActorLocation()).Y < 30.f) return false;
	if (FVector::DistSquared(Cat->GetActorLocation(),Target) > FMath::Square(InteractionRange)) return false;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(Stage3ReleaseReach), true, Cat);
	Params.AddIgnoredActor(D.Housing); Params.AddIgnoredActor(D.Ring);
	if (D.Pin) Params.AddIgnoredActor(D.Pin);
	return !GetWorld()->LineTraceSingleByChannel(Hit,Cat->GetActorLocation(),Target,ECC_Visibility,Params);
}
bool ACatrunStage3Objectives::TryRelease(int32 Index, APawn* Cat)
{
	if (!CanRelease(Index,Cat) || !ReleaseAnimation || MouthOffsets.Num()!=73 || ActiveDevice!=INDEX_NONE) return false;
	auto* Character = Cast<ACharacter>(Cat);
	auto* Controller = Cast<APlayerController>(Cat->GetController());
	auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	if (!Character || !Controller || !Actions) return false;
	auto& D = Devices[Index];
	const FVector Facing = D.Housing->GetActorRotation().RotateVector(FVector(0,-1,0));
	const FRotator Rotation = Facing.Rotation();
	const FVector Bite = D.Ring->GetActorLocation()+D.Housing->GetActorRotation().RotateVector(FVector(0,.9,-6.5));
	const FVector Target = Bite-Rotation.RotateVector(MouthOffsets[24]);
	if (FMath::Abs(Target.Z-Cat->GetActorLocation().Z)>3.f) return false;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(Stage3Alignment),false,Cat);
	const auto* Capsule = Character->GetCapsuleComponent();
	if (GetWorld()->SweepSingleByChannel(Hit,Cat->GetActorLocation(),Target,FQuat::Identity,ECC_Pawn,
		FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(),Capsule->GetScaledCapsuleHalfHeight()),Params)) return false;
	InteractingCat=Character; InteractingController=Controller;
	ActiveDevice=Index; AlignmentElapsed=0.f; bClipStarted=false;
	AlignmentStart=Cat->GetActorLocation(); AlignmentTarget=Target; AlignmentRotation=Rotation;
	RingStart=D.Ring->GetActorLocation(); PinStart=D.Pin ? D.Pin->GetActorLocation() : FVector::ZeroVector;
	auto* Mesh=Character->GetMesh(); auto* Move=Character->GetCharacterMovement();
	SavedAnimMode=Mesh->GetAnimationMode(); SavedAnimClass=Mesh->GetAnimClass(); SavedAnimation=Mesh->AnimationData;
	if (auto* Single=Mesh->GetSingleNodeInstance())
	{
		SavedAnimation.AnimToPlay=Single->GetCurrentAsset(); SavedAnimation.SavedPosition=Single->GetCurrentTime();
		SavedAnimation.SavedPlayRate=Single->GetPlayRate(); SavedAnimation.bSavedLooping=Single->IsLooping(); SavedAnimation.bSavedPlaying=Single->IsPlaying();
	}
	SavedMovementMode=Move->MovementMode; SavedCustomMode=Move->CustomMovementMode;
	Actions->Busy=true; Move->StopMovementImmediately(); Move->DisableMovement(); Controller->SetIgnoreMoveInput(true);
	return true;
}
void ACatrunStage3Objectives::CommitRelease(int32 Index)
{
	auto& D = Devices[Index];
	if (D.bReleased) return;
	D.bReleased = true;
	if (D.LockBolt) D.LockBolt->AddActorWorldOffset(D.LockBolt->GetActorRotation().RotateVector(FVector(0,0,16)));
	if (auto* Grid = ASoundGridManager::Get(this))
	{
		FCatrunSoundEvent Event;
		Event.Source = ECatrunSoundSource::Device; Event.Kind = ECatrunSoundKind::Device;
		Event.Size = ECatrunSoundSize::Large; Event.Location = D.Ring->GetActorLocation(); Event.Instigator = this;
		Grid->EmitSound(Event);
	}
	if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
		Notice->ShowNotice(FText::FromString(AllReleased() ? TEXT("봉쇄 장치 3개 해제. 통제실의 동상을 발판에 놓으세요.") : TEXT("봉쇄 장치를 해제했어요.")),3.f);
}
void ACatrunStage3Objectives::UpdateChain(FCatrunReleaseDevice& D)
{
	if (!D.Pin || !D.Ring) return;
	const FVector Eye=D.Pin->GetActorLocation()+D.Housing->GetActorRotation().RotateVector(FVector(-10,1,-3.2));
	const FVector RingTop=D.Ring->GetActorLocation()+FVector(0,0,7.4);
	const FVector Axis=(Eye-RingTop).GetSafeNormal();
	const FQuat Basis=FRotationMatrix::MakeFromZ(Axis).ToQuat();
	for (int32 I=0;I<D.ChainLinks.Num();++I) if (auto* Link=D.ChainLinks[I].Get())
	{
		const float T=D.ChainLinks.Num()>1 ? float(I)/(D.ChainLinks.Num()-1) : .5f;
		Link->SetActorLocation(FMath::Lerp(RingTop+Axis*2.6,Eye-Axis*5.5,T));
		Link->SetActorRotation(Basis*FQuat(FVector::UpVector,(I%2==0) ? PI*.5f : 0.f));
	}
}
void ACatrunStage3Objectives::UpdateInteraction(float DeltaSeconds)
{
	auto* Cat=InteractingCat.Get();
	const auto* Restart=UCatrunRestartSubsystem::Get(this);
	const auto* Flow=UCatrunLevelFlowSubsystem::Get(this);
	if (!Cat || !Devices.IsValidIndex(ActiveDevice) || (Restart && Restart->IsCatching())
		|| (Flow && (Flow->IsTransitioning() || Flow->IsStageComplete()))) { FinishInteraction(true); return; }
	auto& D=Devices[ActiveDevice];
	if (!IsValid(D.Ring) || !IsValid(D.Housing)) { FinishInteraction(true); return; }
	if (!bClipStarted)
	{
		AlignmentElapsed+=DeltaSeconds;
		const float T=FMath::Clamp(AlignmentElapsed/.2f,0.f,1.f);
		FHitResult Hit; Cat->SetActorLocation(FMath::Lerp(AlignmentStart,AlignmentTarget,FMath::SmoothStep(0.f,1.f,T)),true,&Hit);
		if (Hit.bBlockingHit) { FinishInteraction(true); return; }
		Cat->SetActorRotation(AlignmentRotation);
		if (T>=1.f) { Cat->GetMesh()->PlayAnimation(ReleaseAnimation,false); bClipStarted=true; }
		return;
	}
	auto* Single=Cat->GetMesh()->GetSingleNodeInstance();
	if (!Single || Single->GetCurrentAsset()!=ReleaseAnimation) { FinishInteraction(true); return; }
	const float Time=Single->GetCurrentTime();
	if (Time>=24.f/30.f)
	{
		const float Frame=FMath::Clamp(Time*30.f,24.f,48.f);
		const int32 Lo=FMath::FloorToInt(Frame), Hi=FMath::Min(Lo+1,48);
		const FVector Mouth=FMath::Lerp(MouthOffsets[Lo],MouthOffsets[Hi],Frame-Lo);
		D.Ring->SetActorLocation(RingStart+AlignmentRotation.RotateVector(Mouth-MouthOffsets[24]));
	}
	const float Withdrawal=FMath::SmoothStep(29.f/30.f,44.f/30.f,Time);
	if (D.Pin) D.Pin->SetActorLocation(PinStart+D.Housing->GetActorRotation().RotateVector(FVector(-14.f*Withdrawal,0,0)));
	UpdateChain(D);
	if (Time>=44.f/30.f) CommitRelease(ActiveDevice);
	if (Time>=ReleaseAnimation->GetPlayLength()-.001f) FinishInteraction(false);
}
void ACatrunStage3Objectives::FinishInteraction(bool bInterrupted)
{
	if (ActiveDevice==INDEX_NONE) return;
	const int32 Previous=ActiveDevice; ActiveDevice=INDEX_NONE;
	if (Devices.IsValidIndex(Previous) && !Devices[Previous].bReleased)
	{
		auto& D=Devices[Previous]; if (D.Ring) D.Ring->SetActorLocation(RingStart); if (D.Pin) D.Pin->SetActorLocation(PinStart); UpdateChain(D);
	}
	if (auto* PC=InteractingController.Get()) PC->SetIgnoreMoveInput(false);
	if (auto* Cat=InteractingCat.Get())
	{
		const auto* Restart=UCatrunRestartSubsystem::Get(this);
		const bool bCaptured=Restart && Restart->IsCatching();
		auto* Mesh=Cat->GetMesh(); auto* Single=Mesh->GetSingleNodeInstance();
		// Do not overwrite a newer animation owner (capture, travel or another sequence).
		if (!bCaptured && (!bClipStarted || (Single && Single->GetCurrentAsset()==ReleaseAnimation)))
		{
			Mesh->SetAnimInstanceClass(SavedAnimClass); Mesh->AnimationData=SavedAnimation; Mesh->SetAnimationMode(SavedAnimMode,true);
			if (SavedAnimMode==EAnimationMode::AnimationSingleNode)
			{
				Mesh->PlayAnimation(SavedAnimation.AnimToPlay,SavedAnimation.bSavedLooping); Mesh->SetPosition(SavedAnimation.SavedPosition,false);
				Mesh->SetPlayRate(SavedAnimation.SavedPlayRate); if (!SavedAnimation.bSavedPlaying) Mesh->Stop();
			}
		}
		// Animation ownership and the movement lock are independent. Releasing our
		// clip after an animation override must not strand the player in MOVE_None.
		const auto* Flow=UCatrunLevelFlowSubsystem::Get(this);
		if (!bCaptured && !(Flow && (Flow->IsTransitioning() || Flow->IsStageComplete()))
			&& Cat->GetCharacterMovement()->MovementMode==MOVE_None)
			Cat->GetCharacterMovement()->SetMovementMode(static_cast<EMovementMode>(SavedMovementMode),SavedCustomMode);
		if (auto* Actions=Cat->FindComponentByClass<UCatrunBasketInteractionComponent>())
			if (!Actions->bBellActive && Actions->BasketPhase==ECatrunBasketPhase::Outside) Actions->Busy=false;
	}
	InteractingCat.Reset(); InteractingController.Reset(); bClipStarted=false;
}
void ACatrunStage3Objectives::EndPlay(const EEndPlayReason::Type Reason)
{
	FinishInteraction(true); Super::EndPlay(Reason);
}
void ACatrunStage3Objectives::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (ActiveDevice!=INDEX_NONE) { UpdateInteraction(DeltaSeconds); return; }
	APawn* Cat = UGameplayStatics::GetPlayerPawn(this,0);
	if (!GameplayAvailable(Cat)) return;
	if (Puzzle) for (auto& Link : Puzzle->Links)
		if (Link.PuzzleId == LockedPuzzleId) Link.bExternalGateUnlocked = AllReleased();
	int32 Nearest = INDEX_NONE; double Best = FMath::Square(InteractionRange);
	for (int32 I=0; I<Devices.Num(); ++I) if (CanRelease(I,Cat))
	{
		const double Distance = FVector::DistSquared(Cat->GetActorLocation(),Devices[I].Ring->GetActorLocation());
		if (Distance<Best) { Best=Distance; Nearest=I; }
	}
	PromptTime -= DeltaSeconds;
	if (Nearest != INDEX_NONE)
	{
		const FKey Key = UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Interact);
		if (Nearest!=PromptIndex || PromptTime<=0.f)
		{
			if (auto* Notice = UCatrunNoticeSubsystem::Get(this)) Notice->ShowNotice(FText::Format(NSLOCTEXT("Catrun","Stage3ReleaseHint","[{0}] 봉쇄 고리 당기기"),Key.GetDisplayName()),2.f);
			PromptTime=1.8f;
		}
		if (Cast<APlayerController>(Cat->GetController())->WasInputKeyJustPressed(Key)) TryRelease(Nearest,Cat);
	}
	PromptIndex=Nearest;
	if (!FinalLeafLeft || !FinalLeafRight || !AllReleased() || !Puzzle || !Puzzle->IsPuzzleSeated(LockedPuzzleId)) return;
	// The independent final gate opens only at the final hall. Existing D1/D2 remain statue-driven.
	if (!bFinalGateOpen && FVector::DistSquared2D(Cat->GetActorLocation(),(LeftStart+RightStart)*.5)>FMath::Square(400.f)) return;
	bFinalGateOpen=true;
	FinalOffset=FMath::FInterpConstantTo(FinalOffset,310.f,DeltaSeconds,90.f);
	FinalLeafLeft->SetActorLocation(LeftStart-FVector(FinalOffset,0,0));
	FinalLeafRight->SetActorLocation(RightStart+FVector(FinalOffset,0,0));
	if (FinalOffset>=310.f) SetActorTickEnabled(false);
}
