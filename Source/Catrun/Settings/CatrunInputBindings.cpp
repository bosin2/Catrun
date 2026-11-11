#include "CatrunInputBindings.h"
#include "CatrunUserSettings.h"
#include "CatrunSettingsSubsystem.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "EnhancedInputSubsystems.h"
#include "EnhancedPlayerInput.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/InputSettings.h"
#include "GameFramework/PlayerController.h"

FCatrunKeyboardBindings::FCatrunKeyboardBindings()
 : Keys{EKeys::W,EKeys::S,EKeys::A,EKeys::D,EKeys::LeftShift,EKeys::LeftControl,EKeys::SpaceBar,EKeys::F} {}
FKey FCatrunKeyboardBindings::Get(ECatrunInputSlot Slot) const
{
 const int32 Index = static_cast<int32>(Slot);
 return Keys.IsValidIndex(Index) ? Keys[Index] : FKey();
}
bool UCatrunInputBindings::IsKeyboardKey(FKey Key)
{
 const auto* InputSettings=GetDefault<UInputSettings>();
 return Key.IsValid() && Key.IsBindableToActions() && !Key.IsVirtual() && !Key.IsGesture() && !Key.IsButtonAxis()
  && Key.GetMenuCategory()==EKeys::NAME_KeyboardCategory && !Key.IsGamepadKey() && !Key.IsMouseButton() && !Key.IsAxis1D() && !Key.IsAxis2D() && !Key.IsAxis3D()
  && !Key.IsTouch() && Key != EKeys::Escape && Key != EKeys::AnyKey
  && !(Key == EKeys::F11 && InputSettings->bF11TogglesFullscreen) && !InputSettings->ConsoleKeys.Contains(Key);
}
FText UCatrunInputBindings::GetInvalidKeyboardKeyMessage()
{
 return NSLOCTEXT("Catrun","BindingInvalid","Esc와 시스템 예약 키를 제외한 키보드 키 하나를 지정하세요.");
}
bool FCatrunKeyboardBindings::Validate(FText& Error) const
{
 Error = FText::GetEmpty();
 if (Keys.Num() != 8) { Error = NSLOCTEXT("Catrun","BindingCount","모든 조작 키를 지정하세요."); return false; }
 TSet<FKey> Seen;
 for (const FKey& Key : Keys)
 {
  if (!UCatrunInputBindings::IsKeyboardKey(Key)) { Error = UCatrunInputBindings::GetInvalidKeyboardKeyMessage(); return false; }
  if (Seen.Contains(Key)) { Error = NSLOCTEXT("Catrun","BindingDuplicate","같은 키를 두 조작에 지정할 수 없습니다."); return false; }
  Seen.Add(Key);
 }
 return true;
}
FKey UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot Slot)
{
 const auto* Settings = UCatrunUserSettings::GetCatrunUserSettings();
 return Settings ? Settings->GetKeyboardBindings().Get(Slot) : FCatrunKeyboardBindings().Get(Slot);
}
FText UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot Slot) { return GetEffectiveKey(Slot).GetDisplayName(); }
FVector2D UCatrunInputBindings::GetMovementInput(TFunctionRef<bool(FKey)> IsDown)
{
 return FVector2D(float(IsDown(GetEffectiveKey(ECatrunInputSlot::Forward)))-float(IsDown(GetEffectiveKey(ECatrunInputSlot::Back))),
  float(IsDown(GetEffectiveKey(ECatrunInputSlot::Right)))-float(IsDown(GetEffectiveKey(ECatrunInputSlot::Left))));
}
bool UCatrunInputBindings::IsGameplayContext(const UInputMappingContext* Context)
{
 return Context && (Context->GetPathName() == TEXT("/Game/Input/Contexts/IMC_Default.IMC_Default")
  || Context->GetPathName() == TEXT("/Game/Input/Contexts/IMC_CatInteraction.IMC_CatInteraction"));
}
void UCatrunInputBindings::RemapContext(UInputMappingContext* Copy, const UInputMappingContext* Original, const FCatrunKeyboardBindings& Bindings)
{
 if (!Copy || !Original || Copy == Original) return;
 const auto& Mappings = Original->GetMappings();
 if (Copy->GetMappings().Num()!=Mappings.Num()) return;
 for (int32 Index=0; Index<Mappings.Num(); ++Index)
 {
  const auto& Mapping = Mappings[Index];
  if (!Mapping.Action || Mapping.Key.IsGamepadKey() || Mapping.Key.IsAxis1D() || Mapping.Key.IsAxis2D() || Mapping.Key.IsAxis3D()) continue;
  const FString Name = Mapping.Action->GetName();
  int32 Slot = INDEX_NONE;
  if (Name == TEXT("IA_Move"))
  {
   if (Mapping.Key == EKeys::W) Slot=0;
   else if (Mapping.Key == EKeys::S) Slot=1;
   else if (Mapping.Key == EKeys::A) Slot=2;
   else if (Mapping.Key == EKeys::D) Slot=3;
  }
  else if (Name == TEXT("IA_Run")) Slot=4;
  else if (Name == TEXT("IA_Sneak")) Slot=5;
  else if (Name == TEXT("IA_Bell")) Slot=6;
  else if (Name == TEXT("IA_Interact")) Slot=7;
  // Duplicate authored left/right modifier aliases map to the one chosen semantic key.
  if (Slot != INDEX_NONE && Bindings.Keys.IsValidIndex(Slot)) Copy->GetMapping(Index).Key=Bindings.Keys[Slot];
 }
}

bool UCatrunInputBindingSubsystem::IsTickable() const
{
 return !IsTemplate() && GetLocalPlayer() && GetWorld() && GetWorld()->IsGameWorld();
}
TStatId UCatrunInputBindingSubsystem::GetStatId() const
{
 RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunInputBindingSubsystem, STATGROUP_Tickables);
}
void UCatrunInputBindingSubsystem::Tick(float)
{
 // Key edits and late mapping additions already notify us through delegates.
 // Poll only the input-owner lifetime; avoid context searches/copies every frame.
 auto* Input=GetLocalPlayer() ? GetLocalPlayer()->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
 if (Input!=InputSubsystem.Get() || (Input && Input->GetPlayerInput()!=LastPlayerInput.Get())) RefreshBindings();
}
void UCatrunInputBindingSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
 Super::Initialize(Collection);
 BindingsChangedHandle=UCatrunUserSettings::OnKeyboardBindingsChanged.AddUObject(this,&UCatrunInputBindingSubsystem::RefreshBindings);
}
void UCatrunInputBindingSubsystem::Deinitialize()
{
 UCatrunUserSettings::OnKeyboardBindingsChanged.Remove(BindingsChangedHandle);
 if (auto* Input=InputSubsystem.Get())
 {
  Input->OnMappingContextAdded.RemoveDynamic(this,&UCatrunInputBindingSubsystem::ContextAdded);
  Input->OnMappingContextRemoved.RemoveDynamic(this,&UCatrunInputBindingSubsystem::ContextRemoved);
 }
 ContextCopies.Reset();
 Super::Deinitialize();
}
void UCatrunInputBindingSubsystem::ContextAdded(const UInputMappingContext* Context)
{
 if (!bReplacing && UCatrunInputBindings::IsGameplayContext(Context)) RefreshBindings();
}
void UCatrunInputBindingSubsystem::ContextRemoved(const UInputMappingContext* Context)
{
 if (bReplacing) return;
 // Blueprint RemoveMappingContext(original) still owns the lifetime of its replacement.
 if (auto* Copy=ContextCopies.Find(const_cast<UInputMappingContext*>(Context)))
  if (auto* Input=InputSubsystem.Get())
  {
   TGuardValue<bool> Guard(bReplacing,true);
   Input->RemoveMappingContext(*Copy);
  }
}
void UCatrunInputBindingSubsystem::RefreshBindings()
{
 if (bReplacing || !GetLocalPlayer()) return;
 auto* Input=GetLocalPlayer()->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>();
 if (!Input || !Input->GetPlayerInput()) return;
 if (InputSubsystem.Get()!=Input)
 {
  InputSubsystem=Input;
  Input->OnMappingContextAdded.AddUniqueDynamic(this,&UCatrunInputBindingSubsystem::ContextAdded);
  Input->OnMappingContextRemoved.AddUniqueDynamic(this,&UCatrunInputBindingSubsystem::ContextRemoved);
 }
 if (LastPlayerInput.Get()!=Input->GetPlayerInput())
 {
  ContextCopies.Reset();
  LastPlayerInput=Input->GetPlayerInput();
 }
 const auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 const FCatrunKeyboardBindings Bindings=Settings ? Settings->GetKeyboardBindings() : FCatrunKeyboardBindings();
 const bool bKeysChanged=Bindings!=LastBindings;
 TGuardValue<bool> Guard(bReplacing,true);
 FModifyContextOptions Options;
 Options.bIgnoreAllPressedKeysUntilRelease=true;
 // The public subsystem query preserves each known authored context's priority.
 // Do not access UEnhancedPlayerInput's protected applied-context storage.
 TArray<TPair<UInputMappingContext*,int32>> Applied;
 for (const TCHAR* Path : {TEXT("/Game/Input/Contexts/IMC_Default.IMC_Default"),TEXT("/Game/Input/Contexts/IMC_CatInteraction.IMC_CatInteraction")})
 {
  auto* Context=FindObject<UInputMappingContext>(nullptr,Path);
  int32 Priority=0;
  if (Context && Input->HasMappingContext(Context,Priority)) Applied.Emplace(Context,Priority);
 }
 bool bChanged=false;
 for (const auto& Entry : Applied)
 {
  auto* Original=Entry.Key;
  auto* Copy=ContextCopies.FindRef(Original).Get();
  if (!Copy)
  {
   Copy=DuplicateObject<UInputMappingContext>(Original,this,MakeUniqueObjectName(this,UInputMappingContext::StaticClass(),TEXT("CatrunRuntimeMapping")));
   ContextCopies.Add(Original,Copy);
  }
  UCatrunInputBindings::RemapContext(Copy,Original,Bindings);
  Input->RemoveMappingContext(Original,Options);
  Input->AddMappingContext(Copy,Entry.Value,Options);
  bChanged=true;
 }
 if (bKeysChanged)
  for (const auto& Pair : ContextCopies)
   UCatrunInputBindings::RemapContext(Pair.Value,Pair.Key,Bindings);
 if (bKeysChanged || bChanged)
 {
  if (auto* SettingsUI=UCatrunSettingsSubsystem::Get(this)) SettingsUI->IgnoreHeldKeysUntilRelease();
  if (auto* PC=GetLocalPlayer()->GetPlayerController(GetWorld())) PC->FlushPressedKeys();
  Input->RequestRebuildControlMappings(Options,EInputMappingRebuildType::RebuildWithFlush);
 }
 LastBindings=Bindings;
}
