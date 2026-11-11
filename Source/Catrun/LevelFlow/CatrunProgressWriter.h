#pragma once
#include "CoreMinimal.h"
#include "Delegates/Delegate.h"

class ISaveGameSystem;

/** One slot, one operation at a time. In-flight I/O outlives its UI/world. */
class CATRUN_API FCatrunProgressWriter : public TSharedFromThis<FCatrunProgressWriter>
{
public:
	using FResult = TFunction<void(bool, const FString&)>;
	using FPayload = TFunction<bool(TArray<uint8>&)>;
	FCatrunProgressWriter();
	explicit FCatrunProgressWriter(ISaveGameSystem* InBackend) : Backend(InBackend) {}
	uint64 Enqueue(FPayload Payload, FResult Result);
	bool IsBusy() const { return bBusy || !Queue.IsEmpty(); }
	FSimpleDelegate OnIdle;
private:
	struct FOperation
	{
		uint64 Id = 0;
		FPayload Payload;
		FResult Result;
		TArray<uint8> Previous;
		TSharedPtr<const TArray<uint8>> Data;
		bool bHadPrevious = false;
	};
	void StartNext();
	void Write();
	void Finish(bool bSuccess, const FString& Error);
	ISaveGameSystem* Backend = nullptr;
	bool bWritesAtomically = false;
	TArray<FOperation> Queue;
	FOperation Active;
	uint64 NextId = 0;
	bool bBusy = false;
};
