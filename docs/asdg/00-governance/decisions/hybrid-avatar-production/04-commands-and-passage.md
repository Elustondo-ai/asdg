# Commands and a fixed comparison passage

These commands make the proposed experiment reviewable. Only the regression and metadata checks described in the inventory were executed. Setup, model acquisition, synthesis and rebuilding remain pending authorization. Run baseline commands from the standalone ASDG root.

```sh
python3 -B -m unittest discover -s build/publication-pipeline -p 'test_*.py' -v
build/publication-pipeline/asdg-publish-presentations scan --presentation nov-2026-11-05-expanded-28 --dry-run
# Proposed Gate 0, after authorization: uses existing assets and revalidates caches.
build/publication-pipeline/asdg-publish-presentations build --presentation nov-2026-11-05-expanded-28 --changed-only
```

A changed-only run measures validation/cache reuse, not original synthesis time. A separately scoped one-slide rebuild in a new output folder is needed for cold baseline cost/runtime. Never remove the established cache or upload ledger to force it. The current wrapper selects its bundled Python; set `ASDG_PUBLISH_PYTHON` only to an inspected compatible runtime.

The following upstream CLI smoke recipe requires an approved installed runtime and complete approved local model snapshot. It is not the proposed integrated adapter. `ASDG_VOICE_PRIVATE` must already point to a selected non-synced private folder; `ASDG_QWEN_MODEL` must point to the complete local model. No download command is authorized or included. All dependencies and transitive wheels must first be pinned and reviewed.

```sh
test -d "$ASDG_VOICE_PRIVATE"
test -d "$ASDG_QWEN_MODEL"
# After setup approval, create a separate environment at this private location.
/opt/homebrew/bin/python3.11 -m venv "$ASDG_VOICE_PRIVATE/venv"
# Install only the reviewed lockfile; its exact versions are a pending deliverable.
# Network must also be disabled for the inference process, beyond these HF flags.
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
  "$ASDG_VOICE_PRIVATE/venv/bin/python" -m mlx_audio.tts.generate \
  --model "$ASDG_QWEN_MODEL" \
  --ref_audio "$ASDG_VOICE_PRIVATE/reference.wav" \
  --ref_text "$(cat "$ASDG_VOICE_PRIVATE/reference.txt")" \
  --output_path "$ASDG_VOICE_PRIVATE/qwen-run-01" \
  --file_prefix technical-passage --audio_format wav --join_audio \
  < "$ASDG_VOICE_PRIVATE/technical-passage.txt"
```

The [inspected CLI source](https://github.com/Neywa-Labs/mlx-audio/blob/main/mlx_audio/tts/generate.py) reads target text from stdin and reference transcript as a literal string, not a filename. It exposes no `--seed` flag in the inspected revision. Confirm flags against the pinned installed version before running. Default missing-transcript handling can load ASR; this protocol supplies the transcript explicitly. Offline flags alone do not prove absence of all network traffic.

Use this exact passage for Pablo, Kokoro and Qwen. At 135 words per minute it is approximately one minute; measured duration determines acceptance. Review acronym pronunciation separately; preserve the same source text and audit any spoken expansion.

> ASDG stands for Agentic Software Development Governance. It helps a human and a team of agents preserve purpose, evidence, and responsibility while building software. A plan describes intended work. A test result describes observed behavior. Human approval is a separate decision. In this experiment, the slides remain unchanged while a local voice model reads the speaker notes. The production pipeline measures each audio segment, aligns the captions, and combines the result with FFmpeg. If a note changes, only the affected narration and scene should be regenerated. We will check pronunciation of ASDG, Qwen, MLX, MCP, and UML, as well as version three point one and a duration of forty-five minutes. The final question is practical: does this sound like Pablo, and would he choose to use it for a technical presentation?

Planned harness outputs are `qwen-run-01/`, `qwen-run-02/`, `kokoro/`, `human/`, a private run manifest and a listening score sheet. Shareable reports contain aggregate timings and scores only. Keep the reference audio, embeddings, comparison readings and synthesis privately local until explicit further consent.

See [the experiment protocol](03-voice-experiment.md) for prerequisites and acceptance. This reference appendix uses the explanatory visual embedded there.
