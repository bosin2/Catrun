#pragma once

#include "CoreMinimal.h"

class APawn;
class UObject;

/**
 * Small helpers to find the player's cat and ask about its state.
 * Used by every monster so they all see the cat the same way.
 */
namespace CatrunCat
{
	// The cat the player controls, or nullptr.
	CATRUN_API APawn* Find(const UObject* WorldContextObject);

	// True while the cat is hiding (in a basket and so on). Hiding cats cannot be seen.
	// This reads the "IsHidden" variable of the cat's own interaction component (read only,
	// the cat's blueprint is never edited).
	CATRUN_API bool IsHiding(const APawn* Cat);
}
