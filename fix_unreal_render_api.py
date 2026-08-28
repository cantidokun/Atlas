from pathlib import Path

path = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")
text = path.read_text(encoding="utf-8")

replacements = {
    "Config->FindSettingByClass<UMoviePipelineOutputSetting>(false)":
        "Cast<UMoviePipelineOutputSetting>(Config->FindSettingByClass(UMoviePipelineOutputSetting::StaticClass(), false, true))",
    "Config->FindSettingByClass<UMoviePipelineImageSequenceOutput_PNG>(false)":
        "Cast<UMoviePipelineImageSequenceOutput_PNG>(Config->FindSettingByClass(UMoviePipelineImageSequenceOutput_PNG::StaticClass(), false, true))",
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one occurrence of {old!r}, found {count}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("Applied UE5.6 Movie Render Pipeline API compatibility fixes to AtlasTransportServer.cpp")
