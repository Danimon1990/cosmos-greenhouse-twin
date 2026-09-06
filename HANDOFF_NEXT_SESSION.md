# Greenhouse Kit Streaming — continuation note

## Current result

- The presentation scene opens successfully in the local Kit USD Viewer.
- The original greenhouse scene remains untouched; the streaming demo is:
  `/home/daniel/Documents/cosmos-greenhouse-twin/usd/scenes/greenhouse_streaming_demo.usda`.
- The demo includes four cameras, hides the robot, and the existing `com.greenhouse.gantry` extension has camera buttons plus a greenhouse-roof visibility toggle.

## Kit app integration

The generated Kit application lives at:

`/home/daniel/Documents/Omniverse/kit-app-template`

The base viewer, streaming viewer, and NVCF layer now register the greenhouse repository extension folder:

`/home/daniel/Documents/cosmos-greenhouse-twin/exts`

The streaming layer must contain this folder itself because Kit resolves its dependencies before it loads the base viewer's settings. This was the cause of the prior error:

`No versions of com.greenhouse.gantry that satisfies ...`

## Next step

The rebuild was started but intentionally interrupted when stopping for the day. Resume with:

```bash
cd /home/daniel/Documents/Omniverse/kit-app-template
./repo.sh build
```

If it succeeds, launch the stream-capable app:

```bash
./repo.sh launch
```

Choose `greenhouse.my_usd_viewer_streaming.kit`.

Expected result: the greenhouse demo loads automatically and a **Greenhouse Gantry + Cosmos** controls panel appears. Test **Exterior**, **Interior**, and **Hide greenhouse top** first.

## Notes

- The IOMMU warning is unrelated to the blank-viewer issue. The blank viewer was caused by a line-wrapped USD path in a manual launch command; auto-loading the USD from the `.kit` config avoids that.
- Do not use `--no-window` while validating the embedded Omniverse UI. Headless/WebRTC comes after this control-panel check.
- Next major milestone after the Kit panel works: run local WebRTC streaming, then add a small React client using `@nvidia/ov-web-rtc` and bridge web buttons to Kit messaging.
