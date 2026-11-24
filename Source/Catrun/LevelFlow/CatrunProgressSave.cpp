#include "CatrunProgressSave.h"
#include "Misc/EngineVersion.h"
#include "Serialization/CustomVersion.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/ObjectAndNameAsStringProxyArchive.h"
#include "UObject/ObjectVersion.h"
#include "UObject/PropertyTypeName.h"
#include "UObject/UnrealType.h"

namespace
{
class FCatrunSaveReader : public FMemoryReader
{
public:
	explicit FCatrunSaveReader(const TArray<uint8>& Bytes) : FMemoryReader(Bytes, true)
	{
		ArMaxSerializeSize = Bytes.Num();
	}
};

// UE normally skips or converts unrecognized property tags. A checkpoint that loses a
// field that way cannot be a safe baseline for replacing the user's slot. Let UE read
// the object framing and values, validating each tagged scalar before it is consumed.
class FCatrunProgressArchive final : public FObjectAndNameAsStringProxyArchive
{
public:
	FCatrunProgressArchive(FArchive& Reader, const TArray<uint8>& Bytes)
		: FObjectAndNameAsStringProxyArchive(Reader, false), Data(Bytes) {}

	bool HasStageFields() const
	{
		return Seen.Contains(GET_MEMBER_NAME_CHECKED(UCatrunProgressSave, Stage1RemainingMs))
			|| Seen.Contains(GET_MEMBER_NAME_CHECKED(UCatrunProgressSave, Stage2RemainingMs))
			|| Seen.Contains(GET_MEMBER_NAME_CHECKED(UCatrunProgressSave, Stage2SolvedMask));
	}

	FArchive& operator<<(FName& Name) override
	{
		const bool bFieldName = !bFinishedTags && Tell() >= NextTag;
		FNameAsStringProxyArchive::operator<<(Name);
		if (!bFieldName) return *this;
		if (Name.IsNone()) bFinishedTags = true;
		else if (!ValidateField(Name))
		{
			Name = NAME_None;
			SetCriticalError();
		}
		return *this;
	}

private:
	bool ValidateField(FName Name)
	{
		const FProperty* Property = FindFProperty<FProperty>(UCatrunProgressSave::StaticClass(), Name);
		if (!Property || !Property->HasAnyPropertyFlags(CPF_SaveGame) || Seen.Contains(Name)) return false;
		Seen.Add(Name);
		// Compare with UE's encoding of the full reflected type (including DateTime's
		// struct path), without parsing an untrusted recursive type descriptor.
		TArray<uint8> TypeBytes;
		FMemoryWriter Writer(TypeBytes, true);
		FNameAsStringProxyArchive Names(Writer);
		UE::FPropertyTypeName Type(Property);
		Names << Type;
		const int64 SizeOffset = Tell() + TypeBytes.Num();
		const int64 ValueOffset = SizeOffset + sizeof(int32) + 1;
		if (ValueOffset > Data.Num() || FMemory::Memcmp(Data.GetData() + Tell(), TypeBytes.GetData(), TypeBytes.Num())) return false;
		int32 Size = 0;
		FMemory::Memcpy(&Size, Data.GetData() + SizeOffset, sizeof(Size));
		if (Size < 0 || Size > Data.Num() - ValueOffset) return false;
		const bool bBool = CastField<FBoolProperty>(Property) != nullptr;
		// Catrun's scalar fields have no static-array index, property GUID, extensions
		// or skipped value; only the native-serialization and boolean-value bits apply.
		const uint8 Flags = Data[ValueOffset - 1];
		if ((Flags & ~(bBool ? 0x18 : 0x08)) != 0) return false;
		NextTag = ValueOffset + Size;
		if (CastField<FNameProperty>(Property))
		{
			if (Size < int32(sizeof(int32))) return false;
			int32 Length = 0;
			FMemory::Memcpy(&Length, Data.GetData() + ValueOffset, sizeof(Length));
			const int64 EncodedSize = Length < 0 ? -int64(Length) * sizeof(UTF16CHAR) : int64(Length);
			return int64(Size) == int64(sizeof(int32)) + EncodedSize;
		}
		return Size == (bBool ? 0 : Property->GetSize());
	}

	const TArray<uint8>& Data;
	TSet<FName> Seen;
	int64 NextTag = 0;
	bool bFinishedTags = false;
};
}

const UCatrunProgressSave* UCatrunProgressSave::Decode(const TArray<uint8>& Data)
{
	// Catrun schemas 1-4 all use the UE5 GVAS v3 envelope. The generic loader
	// can return a partially deserialized object and accepts arbitrary class paths.
	FCatrunSaveReader Reader(Data);
	uint32 Tag = 0;
	int32 Envelope = 0;
	Reader << Tag << Envelope;
	if (Tag != 0x53415647 || Envelope != 3) return nullptr;
	FPackageFileVersion PackageVersion;
	FEngineVersion EngineVersion;
	Reader << PackageVersion << EngineVersion;
	if (Reader.IsError() || PackageVersion.ToValue() > GPackageFileUEVersion.ToValue()) return nullptr;
	Reader.SetUEVer(PackageVersion);
	Reader.SetEngineVer(EngineVersion);
	int32 Format = 0, Count = 0;
	Reader << Format;
	const int64 TableStart = Reader.Tell();
	Reader << Count;
	if (Format != int32(ECustomVersionSerializationFormat::Optimized) || Reader.IsError() || Count < 0
		|| int64(Count) * int64(sizeof(FGuid) + sizeof(int32)) > Reader.TotalSize() - Reader.Tell()) return nullptr;
	Reader.Seek(TableStart);
	FCustomVersionContainer Versions;
	Versions.Serialize(Reader, ECustomVersionSerializationFormat::Optimized);
	Reader.SetCustomVersions(Versions);
	FString ClassName;
	Reader << ClassName;
	if (Reader.IsError() || ClassName != StaticClass()->GetPathName()) return nullptr;
	auto* Save = NewObject<UCatrunProgressSave>();
	FCatrunProgressArchive Archive(Reader, Data);
	Save->Serialize(Archive);
	if (Save->SchemaVersion < CurrentSchemaVersion && Archive.HasStageFields()) return nullptr;
	return !Reader.IsError() && !Archive.IsError() && Reader.AtEnd() && Save->IsSupported() ? Save : nullptr;
}

bool UCatrunProgressSave::IsSupported() const
{
	if (SchemaVersion < 1 || SchemaVersion > CurrentSchemaVersion) return false;
	return Stage1RemainingMs >= -1 && Stage1RemainingMs <= MaxRemainingMs
		&& Stage2RemainingMs >= -1 && Stage2RemainingMs <= MaxRemainingMs
		&& (Stage2SolvedMask & ~AllPuzzleBits) == 0;
}
