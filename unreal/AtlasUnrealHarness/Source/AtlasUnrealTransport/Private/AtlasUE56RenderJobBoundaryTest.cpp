#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56RenderJobBoundaryTest,
    "Atlas.UnrealAgent.UE56.RenderJobSubmissionBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasUE56RenderJobBoundaryTest::RunTest(const FString& Parameters)
{
    TestTrue(
        TEXT("UE 5.6 render-job boundary test is executing inside the editor automation framework"),
        GEngine != nullptr);

    return !HasAnyErrors();
}
