from pathlib import Path

HEADER = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h")
CPP = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")

header = HEADER.read_text(encoding="utf-8")
cpp = CPP.read_text(encoding="utf-8")

# Keep the production header declaration clean and idempotent.
header = header.replace(
    "      static bool SetBlueprintMetadata(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);     static bool BuildBlueprintState",
    "    static bool SetBlueprintMetadata(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool BuildBlueprintState",
)
if "static bool SetBlueprintMetadata(" not in header:
    needle = "    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);"
    if needle not in header:
        raise SystemExit("Could not find CompileBlueprint declaration in header.")
    header = header.replace(
        needle,
        needle + "\n    static bool SetBlueprintMetadata(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);",
    )

# UE 5.6 uses FMetaData (not the removed UMetaData type).
if '#include "UObject/MetaData.h"' not in cpp:
    needle = '#include "Kismet2/KismetEditorUtilities.h"'
    if needle not in cpp:
        raise SystemExit("Could not find KismetEditorUtilities include.")
    cpp = cpp.replace(needle, needle + '\n#include "UObject/MetaData.h"')

old = '''    if(Blueprint->GeneratedClass) State->SetStringField(TEXT("generated_class"),Blueprint->GeneratedClass->GetPathName());
    else State->SetStringField(TEXT("generated_class"),TEXT(""));
    O=State;
    return true;'''

new = '''    if(Blueprint->GeneratedClass) State->SetStringField(TEXT("generated_class"),Blueprint->GeneratedClass->GetPathName());
    else State->SetStringField(TEXT("generated_class"),TEXT(""));

    TSharedPtr<FJsonObject> Metadata = MakeShareable(new FJsonObject);
    if (TMap<FName, FString>* MetadataValues = FMetaData::GetMapForObject(Blueprint))
    {
        for (const TPair<FName, FString>& Pair : *MetadataValues)
        {
            Metadata->SetStringField(Pair.Key.ToString(), Pair.Value);
        }
    }
    State->SetObjectField(TEXT("metadata"), Metadata);

    O=State;
    return true;'''

if old not in cpp:
    if 'State->SetObjectField(TEXT("metadata"), Metadata);' not in cpp:
        raise SystemExit("Could not find BuildBlueprintState insertion point.")
else:
    cpp = cpp.replace(old, new, 1)

HEADER.write_text(header, encoding="utf-8")
CPP.write_text(cpp, encoding="utf-8")
print("Applied Unreal Blueprint metadata evidence fix.")
