#pragma once
#include "CoreMinimal.h"

// Shared palette authored in sRGB, converted for Slate.
namespace CatrunHUDStyle
{
 inline const FLinearColor Ink = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("211F1C")));
 inline const FLinearColor Brass = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("B8A17A")));
 inline const FLinearColor Rim = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("756956")));
 inline const FLinearColor Parchment = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("D5C6A4")));
 inline const FLinearColor Sage = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("B2BE94")));
 inline const FLinearColor Warning = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("D0AA70")));
 inline const FLinearColor Urgent = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("CD8174")));
 inline const FLinearColor MarkerInk = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("171815")));
 inline const FLinearColor CatYellow = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("F4CE55")));
 inline const FLinearColor CatHighlight = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("FFE9A0")));
 inline const FLinearColor ArmorRed = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("E56961")));
 inline const FLinearColor ArmorHighlight = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("FFB2A0")));
 inline const FLinearColor CandleFlame = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("F0A45A")));
 inline const FLinearColor CandleWax = FLinearColor::FromSRGBColor(FColor::FromHex(TEXT("F4EAD4")));
}
