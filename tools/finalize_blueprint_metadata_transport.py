"""Finalize the Blueprint metadata transport migration after enable_blueprint_transport.py.

The transport migration intentionally uses a second deterministic pass for the
metadata enumeration anchor so the existing Blueprint implementation remains
compatible with the UE 5.6 package metadata API.
"""

from pathlib import Path

CPP = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if not CPP.exists():
        raise SystemExit(f"missing transport source: {CPP}")
    text = CPP.read_text(encoding="utf-8")

    if '#include "UObject/MetaData.h"' not in text:
        text = replace_once(
            text,
            '#include "UObject/SavePackage.h"\n',
            '#include "UObject/SavePackage.h"\n#include "UObject/MetaData.h"\n',
            "metadata include",
        )

    bad = '''    const TArray<FName>& MetadataKeys=Blueprint->GetMetaData().GetKeys();
    TSharedPtr<FJsonObject> Metadata=MakeShareable(new FJsonObject);
    for(const FName& Key:MetadataKeys) Metadata->SetStringField(Key.ToString(),Blueprint->GetMetaData(Key));
    State->SetObjectField(TEXT("metadata"),Metadata);
'''
    good = '''    TSharedPtr<FJsonObject> Metadata=MakeShareable(new FJsonObject);
    if(UPackage* Package=Blueprint->GetOutermost())
    {
        FMetaData& PackageMetadata=Package->GetMetaData();
        if(TMap<FName,FString>* MetadataMap=FMetaData::GetMapForObject(Blueprint))
        {
            for(const TPair<FName,FString>& Pair:*MetadataMap)
            {
                Metadata->SetStringField(Pair.Key.ToString(),Pair.Value);
            }
        }
    }
    State->SetObjectField(TEXT("metadata"),Metadata);
'''
    if bad in text:
        text = replace_once(text, bad, good, "Blueprint metadata enumeration")
    elif 'FMetaData::GetMapForObject(Blueprint)' not in text:
        raise SystemExit("Blueprint metadata state implementation is missing; run enable_blueprint_transport.py first")

    CPP.write_text(text, encoding="utf-8")
    print(f"Blueprint metadata state serialization finalized in {CPP}")


if __name__ == "__main__":
    main()
