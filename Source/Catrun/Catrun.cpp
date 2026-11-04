#include "Catrun.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogCatrunSound);

// Map selection is owned by CatrunLevelFlowSettings and explicit Blueprint flow calls.
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Catrun, "Catrun");
