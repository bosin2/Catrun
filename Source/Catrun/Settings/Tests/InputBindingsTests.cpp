#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Settings/CatrunInputBindings.h"
#include "Settings/CatrunUserSettings.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Input/Reply.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Input/SButton.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "InputModifiers.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBindingValidationTest,"Catrun.Settings.KeyboardValidationAndBounds",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBindingValidationTest::RunTest(const FString&)
{
 FCatrunKeyboardBindings Keys;
 FText Error;
 TestTrue(TEXT("Authored defaults are valid"),Keys.Validate(Error));
 TestEqual(TEXT("Bell default is the actual authored SpaceBar"),Keys.Get(ECatrunInputSlot::Bell),EKeys::SpaceBar);
 TestFalse(TEXT("Out-of-range slot is invalid, never reads beyond the draft"),Keys.Get(static_cast<ECatrunInputSlot>(255)).IsValid());
 for (FKey Invalid : {FKey(),EKeys::Escape,EKeys::AnyKey,EKeys::LeftMouseButton,EKeys::MouseX,EKeys::Gamepad_FaceButton_Bottom,EKeys::Gamepad_LeftX})
 {
  auto Draft=Keys; Draft.Keys[6]=Invalid;
  TestFalse(FString::Printf(TEXT("Rejected non-keyboard/reserved key: %s"),*Invalid.ToString()),Draft.Validate(Error));
 }
 auto Short=Keys; Short.Keys.Pop();
 TestFalse(TEXT("Missing slot is rejected"),Short.Validate(Error));
 auto Long=Keys; Long.Keys.Add(EKeys::G);
 TestFalse(TEXT("Extra slot is rejected"),Long.Validate(Error));
 auto Duplicate=Keys; Duplicate.Keys[6]=EKeys::F;
 TestFalse(TEXT("Whole-draft duplicate is rejected"),Duplicate.Validate(Error));
 auto Modifier=Keys; Modifier.Keys[6]=EKeys::LeftAlt;
 TestTrue(TEXT("Standalone modifier is a digital key, unlike a chord"),Modifier.Validate(Error));
 return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBindingAtomicTest,"Catrun.Settings.AtomicDraftAndCorruptFallback",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBindingAtomicTest::RunTest(const FString&)
{
 auto* Settings=NewObject<UCatrunUserSettings>();
 auto Draft=Settings->GetKeyboardBindings();
 Draft.Keys[0]=EKeys::I;
 Draft.Keys[6]=EKeys::B;
 FText Error;
 TestTrue(TEXT("Valid complete draft commits"),Settings->SetKeyboardBindings(Draft,Error));
 const auto Before=Settings->GetKeyboardBindings();
 Draft.Keys[0]=EKeys::K;
 Draft.Keys[7]=EKeys::B;
 TestFalse(TEXT("One duplicate rejects the complete transaction"),Settings->SetKeyboardBindings(Draft,Error));
 TestTrue(TEXT("Earlier valid changes in a rejected draft never leak"),Settings->GetKeyboardBindings()==Before);
 auto* Property=FindFProperty<FStructProperty>(Settings->GetClass(),TEXT("KeyboardBindings"));
 if (!TestNotNull(TEXT("Persisted typed binding property"),Property)) return false;
 auto* Corrupt=Property->ContainerPtrToValuePtr<FCatrunKeyboardBindings>(Settings);
 Corrupt->Keys={EKeys::Escape};
 TestTrue(TEXT("Corrupt stored config reads as complete defaults"),Settings->GetKeyboardBindings()==FCatrunKeyboardBindings());
 return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRemapPreservationTest,"Catrun.Settings.RemapPreservesDirectionAndGamepad",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRemapPreservationTest::RunTest(const FString&)
{
 auto* Original=NewObject<UInputMappingContext>();
 auto* Move=NewObject<UInputAction>(Original,TEXT("IA_Move"));
 auto* Swizzle=NewObject<UInputModifierSwizzleAxis>(Original);
 auto* Negate=NewObject<UInputModifierNegate>(Original);
 Original->MapKey(Move,EKeys::W).Modifiers.Add(Swizzle);
 auto& Back=Original->MapKey(Move,EKeys::S);
 Back.Modifiers.Add(Negate); Back.Modifiers.Add(Swizzle);
 Original->MapKey(Move,EKeys::Gamepad_Left2D);
 auto* Copy=DuplicateObject<UInputMappingContext>(Original,GetTransientPackage(),MakeUniqueObjectName(GetTransientPackage(),UInputMappingContext::StaticClass(),TEXT("CatrunRemapTestCopy")));
 FCatrunKeyboardBindings Draft;
 Draft.Keys[0]=EKeys::Up; Draft.Keys[1]=EKeys::Down;
 UCatrunInputBindings::RemapContext(Copy,Original,Draft);
 TestEqual(TEXT("Forward key remapped in clone"),Copy->GetMappings()[0].Key,EKeys::Up);
 TestEqual(TEXT("Back key remapped in clone"),Copy->GetMappings()[1].Key,EKeys::Down);
 TestEqual(TEXT("Original W never mutated"),Original->GetMappings()[0].Key,EKeys::W);
 UCatrunInputBindings::RemapContext(Original,Original,Draft);
 TestEqual(TEXT("Remapper refuses to mutate its source context"),Original->GetMappings()[0].Key,EKeys::W);
 auto* EmptyCopy=NewObject<UInputMappingContext>();
 UCatrunInputBindings::RemapContext(EmptyCopy,Original,Draft);
 TestEqual(TEXT("Mismatched copy cannot index beyond its mapping array"),EmptyCopy->GetMappings().Num(),0);
 TestEqual(TEXT("Original S never mutated"),Original->GetMappings()[1].Key,EKeys::S);
 TestEqual(TEXT("Gamepad mapping retained"),Copy->GetMappings()[2].Key,EKeys::Gamepad_Left2D);
 TestEqual(TEXT("Back keeps negate then swizzle"),Copy->GetMappings()[1].Modifiers.Num(),2);
 TestTrue(TEXT("Back negate retained"),Copy->GetMappings()[1].Modifiers[0]->IsA<UInputModifierNegate>());
 TestTrue(TEXT("Back swizzle retained"),Copy->GetMappings()[1].Modifiers[1]->IsA<UInputModifierSwizzleAxis>());
 TestTrue(TEXT("Modifiers are cloned, not aliased to shared assets"),Copy->GetMappings()[1].Modifiers[0]!=Negate);
 return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBindingLookupTest,"Catrun.Settings.EffectiveBasketAndBellKeys",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBindingLookupTest::RunTest(const FString&)
{
 auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 if (!TestNotNull(TEXT("Configured native game settings instance"),Settings)) return false;
 const auto Saved=Settings->GetKeyboardBindings();
 auto Draft=FCatrunKeyboardBindings();
 Draft.Keys[0]=EKeys::I; Draft.Keys[1]=EKeys::K; Draft.Keys[2]=EKeys::J; Draft.Keys[3]=EKeys::L;
 Draft.Keys[6]=EKeys::B; Draft.Keys[7]=EKeys::E;
 FText Error;
 if (!TestTrue(TEXT("Apply temporary unsaved bindings"),Settings->SetKeyboardBindings(Draft,Error))) return false;
 const FVector2D BasketInput=UCatrunInputBindings::GetMovementInput([](FKey Key){return Key==EKeys::I || Key==EKeys::L;});
 TestTrue(TEXT("Basket reads rebound forward/right"),BasketInput.Equals(FVector2D(1,1)));
 const FVector2D OldKeys=UCatrunInputBindings::GetMovementInput([](FKey Key){return Key==EKeys::W || Key==EKeys::D;});
 TestTrue(TEXT("Old WASD no longer select basket direction"),OldKeys.IsNearlyZero());
 TestEqual(TEXT("No-bell block and fallback share effective bell lookup"),UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Bell),EKeys::B);
 TestEqual(TEXT("Statue uses effective interaction key"),UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Interact),EKeys::E);
 TestTrue(TEXT("Restore user's bindings without saving"),Settings->SetKeyboardBindings(Saved,Error));
 return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSettingsInputRestorationTest,"Catrun.Settings.FocusCaptureAndLockRestoration",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunSettingsInputRestorationTest::RunTest(const FString&)
{
 // No SlateApplication/native window/platform input is touched. This state adapter models the engine's
 // OnFocusReceived acquisition and ProcessReply semantics using real FReply flags (ordinary capture != raw release).
 const TSharedRef<SWidget> PreviousControl=SNew(SBox);
 const TSharedRef<SWidget> ModalControl=SNew(SBox);
 const TSharedRef<SWidget> PreviousLockOwner=SNew(SBox);
 const TSharedRef<SWidget> ViewportWidget=SNew(SBox);
 for (bool bSavedRaw : {false,true})
  for (bool bSavedLocked : {false,true})
  {
   struct FInputState
   {
    TSharedPtr<SWidget> Captor;
    TSharedPtr<SWidget> LockOwner;
    bool bRaw=true; // Simulate raw capture introduced while the settings overlay was active.
    bool bIgnore=false;
    EMouseCaptureMode Policy=EMouseCaptureMode::CapturePermanently;
    void Process(const FReply& Reply)
    {
     if (Reply.ShouldReleaseMouse()) Captor.Reset();
     if (Reply.GetMouseCaptor()) Captor=Reply.GetMouseCaptor();
     if (Reply.ShouldUseHighPrecisionMouse() && Captor) bRaw=true;
     if (Reply.ShouldReleaseMouse() && !Reply.ShouldUseHighPrecisionMouse()) bRaw=false;
     if (Reply.GetMouseLockWidget()) LockOwner=Reply.GetMouseLockWidget();
     if (Reply.ShouldReleaseMouseLock()) LockOwner.Reset();
    }
   } State;
   State.Captor=ModalControl;
   State.LockOwner=bSavedLocked ? TSharedPtr<SWidget>(PreviousLockOwner) : TSharedPtr<SWidget>();
   FCatrunSettingsSlateSnapshot Snapshot;
   Snapshot.CursorCaptor=PreviousControl;
   Snapshot.bHighPrecision=bSavedRaw;
   bool bFocusWasSuppressed=false;
   Snapshot.RestoreWithCallbacks(
    [&]{State.bIgnore=true; State.Policy=EMouseCaptureMode::NoCapture;},
    [&]
    {
     bFocusWasSuppressed=State.bIgnore && State.Policy==EMouseCaptureMode::NoCapture;
     // The actual standalone FSceneViewport focus callback acquires raw capture/lock when this guard is absent.
     if (!State.bIgnore && State.Policy==EMouseCaptureMode::CapturePermanently)
      State.Process(FReply::Handled().UseHighPrecisionMouseMovement(ViewportWidget).LockMouseToWidget(ViewportWidget));
    },
    [&](const FReply& Reply){State.Process(Reply);},
    [&]{State.bIgnore=false; State.Policy=EMouseCaptureMode::CapturePermanently;});
   TestTrue(TEXT("Focus callback cannot infer a new capture or lock"),bFocusWasSuppressed);
   TestTrue(TEXT("Cursor capture returns to the previous control"),State.Captor==PreviousControl);
   TestEqual(TEXT("Ordinary and raw captures restore their exact prior mode"),State.bRaw,bSavedRaw);
   TestTrue(TEXT("Actual lock ownership remains the previous owner, including an explicit unlocked state"),
    State.LockOwner==(bSavedLocked ? TSharedPtr<SWidget>(PreviousLockOwner) : TSharedPtr<SWidget>()));
   TestFalse(TEXT("Original viewport ignore policy restored after callbacks"),State.bIgnore);
   TestTrue(TEXT("Original permanent-capture policy restored after callbacks"),State.Policy==EMouseCaptureMode::CapturePermanently);
  }
 // OnMouseButtonUp releases the button before invoking OnClicked, while Slate still owns its capture.
 // Exercise that callback without processing any reply or changing native input/capture.
 FCatrunSettingsSlateSnapshot ClickSnapshot;
 TSharedPtr<SButton> OpeningButton;
 bool bClicked=false;
 OpeningButton=SNew(SButton).ClickMethod(EButtonClickMethod::MouseUp).OnClicked_Lambda([&]
 {
  bClicked=true;
  ClickSnapshot.Focus=OpeningButton;
  ClickSnapshot.CaptureCursor(OpeningButton,false);
  return FReply::Handled();
 });
 const FGeometry Geometry=FGeometry::MakeRoot(FVector2f(100,40),FSlateLayoutTransform());
 const TSet<FKey> PressedButtons={EKeys::LeftMouseButton};
 const FPointerEvent Down(0,FVector2f(10,10),FVector2f(10,10),PressedButtons,EKeys::LeftMouseButton,0,FModifierKeysState());
 const TSet<FKey> ReleasedButtons;
 const FPointerEvent Up(0,FVector2f(10,10),FVector2f(10,10),ReleasedButtons,EKeys::LeftMouseButton,0,FModifierKeysState());
 OpeningButton->OnMouseEnter(Geometry,Down);
 OpeningButton->OnMouseButtonDown(Geometry,Down);
 TestTrue(TEXT("Opening button is genuinely pressed before mouse-up"),OpeningButton->IsPressed());
 FCatrunSettingsSlateSnapshot PressedSnapshot;
 PressedSnapshot.CaptureCursor(OpeningButton,false);
 TestTrue(TEXT("An active button capture is retained"),PressedSnapshot.CursorCaptor.Pin()==OpeningButton);
 OpeningButton->OnMouseButtonUp(Geometry,Up);
 TestTrue(TEXT("Real SButton mouse-up ran the opening callback"),bClicked);
 TestFalse(TEXT("Completed opening click is not saved as persistent capture"),ClickSnapshot.CursorCaptor.IsValid());
 bool bReacquiredClick=false;
 bool bFocusRestored=false;
 ClickSnapshot.RestoreWithCallbacks([]{},[&]{bFocusRestored=ClickSnapshot.Focus.Pin()==OpeningButton;},
  [&](const FReply& Reply){bReacquiredClick|=Reply.GetMouseCaptor().IsValid();},[]{});
 TestFalse(TEXT("Closing settings does not recapture the completed opening button"),bReacquiredClick);
 TestTrue(TEXT("Opening button keyboard focus is still restored"),bFocusRestored);
 FCatrunSettingsSlateSnapshot RawSnapshot;
 RawSnapshot.CaptureCursor(OpeningButton,true);
 TestTrue(TEXT("Explicit high-precision ownership remains intact"),RawSnapshot.CursorCaptor.Pin()==OpeningButton && RawSnapshot.bHighPrecision);
 FCatrunSettingsSlateSnapshot CustomSnapshot;
 CustomSnapshot.CaptureCursor(PreviousControl,false);
 TestTrue(TEXT("Custom ordinary capture owner remains intact"),CustomSnapshot.CursorCaptor.Pin()==PreviousControl);
 return true;
}
#endif
