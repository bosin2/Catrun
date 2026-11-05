#pragma once
#include "CoreMinimal.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunExitTransitionComponent.h"
#include "CatrunExitTestTypes.generated.h"

/** Receives the actual reflected inherited BP event without creating presentation assets. */
UCLASS(Transient)
class ACatrunExitTestActor : public ACatrunStageExit
{
    GENERATED_BODY()
public:
    int32 Qualified = 0, Saved = 0, TravelFailures = 0;
    virtual void ProcessEvent(UFunction* Function, void* Params) override
    {
        if (Function->GetFName()==GET_FUNCTION_NAME_CHECKED(ACatrunStageExit,BeginPortalPresentation)) ++Qualified;
        if (Function->GetFName()==GET_FUNCTION_NAME_CHECKED(ACatrunStageExit,ExitCheckpointSaveFinished)) ++Saved;
        if (Function->GetFName()==GET_FUNCTION_NAME_CHECKED(ACatrunStageExit,ExitTravelFailed)) ++TravelFailures;
        Super::ProcessEvent(Function,Params);
    }
};

UCLASS(Transient)
class UCatrunExitTestObserver : public UObject
{
    GENERATED_BODY()
public:
    UPROPERTY() TObjectPtr<UCatrunExitTransitionComponent> Lease;
    int32 Results = 0;
    bool bReleaseOnResult = false;
    bool bLastSuccess = false, bLastTracked = false;
    UFUNCTION() void Saved(bool bSuccess,bool bTracked,FText Status)
    {
        ++Results; bLastSuccess=bSuccess; bLastTracked=bTracked;
        if (bReleaseOnResult) Lease->ReleaseExitLease();
    }
};
