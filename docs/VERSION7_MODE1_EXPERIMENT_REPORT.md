# Version 7 Mode 1 Experiment Report

Date: 2026-07-14

Image tested locally:

```text
amd-hackathon:version7-mode1-local
```

This was a local experimental image built from the working tree after adding:

```text
VERSION7_SCHEDULER_MODE=post_classification_parallel
```

The published GHCR image was not changed by this experiment.

## Mode Definition

Mode 1 uses a full classification barrier:

```text
classify and route every task
then start answer generation
Fireworks tasks and local Ollama tasks may run at the same time
local Ollama tasks remain serial
```

This differs from the published scheduler, where Fireworks tasks begin while later tasks are still being classified and local-answer tasks wait until classification completes.

## Test Conditions

Input: 10 public Track 1 validation examples from the AMD judging/self-check guide.

Runtime:

```text
--memory=4g
--cpus=2
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
ALLOWED_MODELS=accounts/fireworks/models/kimi-k2p7-code,accounts/fireworks/models/minimax-m3
VERSION7_SCHEDULER_MODE=post_classification_parallel
timeout=600 seconds
```

Fireworks API key was injected at runtime and was not written to the image or report.

## Result

Mode 1 completed successfully.

```text
exit_status: 0
elapsed_seconds: 460
results_json: present
task_count: 10
```

Audit summary:

```text
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
batch_completed: 1
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 317
completion_tokens: 1441
total_tokens: 1758
```

Routing:

```text
T01   CODE_GENERATION              fireworks  max_tokens=1000
T01b  CODE_GENERATION              fireworks  max_tokens=1000
T01c  FACTUAL_KNOWLEDGE            fireworks  max_tokens=64
T02   MATHEMATICAL_REASONING       fireworks  max_tokens=400
T02b  MATHEMATICAL_REASONING       fireworks  max_tokens=400
T03   SENTIMENT_CLASSIFICATION     fireworks  max_tokens=64
T03b  SENTIMENT_CLASSIFICATION     fireworks  max_tokens=64
T04   TEXT_SUMMARISATION           ollama     max_tokens=1000
T04b  TEXT_SUMMARISATION           ollama     max_tokens=1000
T05   NAMED_ENTITY_RECOGNITION     ollama     max_tokens=1000
```

Observed answer latencies:

```text
T01   remote  6.385s
T01b  remote  7.416s
T01c  remote  2.209s
T02   remote  3.483s
T02b  remote  3.381s
T03   remote  5.931s
T03b  remote  3.706s
T04   local   52.018s
T04b  local   90.182s
T05   local   105.915s
```

## Judge-Style Quality Notes

Runtime result: pass.

Output schema result: pass.

Likely accuracy result: risky.

Clear passes:

```text
T01
T01b
T02
T02b
T04
T05
```

Likely failures or high-risk outputs:

```text
T01c: answer contains meta-instructions instead of the actual RAM/ROM explanation.
T03: answer is incomplete: "**Positive** - Despite".
T03b: answer contains meta-reasoning and is not a clean one-sentence classification.
T04b: three bullet format is valid, but the first bullet does not cover the expected benefit; coverage is borderline.
```

## Comparison To Published Scheduler Run

Published scheduler run against the same 10 public tasks:

```text
exit_status: 1
elapsed_seconds: 591
results_json: missing
classified: 10
routed: 10
remote_answered: 7
local_answered: 0
failure: Version 7 batch deadline exceeded
```

Mode 1 improved runtime behavior enough to produce official output within the judge limit.

It did not solve answer-quality risk. The remaining quality risk is primarily caused by verbose or meta-style model outputs and incomplete short-answer outputs.

## Conclusion

Mode 1 is materially better than the published scheduler for the public 10-task runtime check because it completed in 460 seconds and wrote valid official output.

Mode 1 alone is not sufficient for final submission confidence because several answers would likely fail or be borderline under the public guide's expected-answer criteria.

## Follow-Up Token-Cap Experiment

Date: 2026-07-14

Local image:

```text
amd-hackathon:version7-mode1-256caps-local
```

Changes tested:

```text
FACTUAL_KNOWLEDGE max_completion_tokens: 64 -> 256
LOGICAL_DEDUCTIVE_REASONING max_completion_tokens: 64 -> 256
NAMED_ENTITY_RECOGNITION max_completion_tokens: 1000 -> 256
```

The local Ollama generation path was also corrected to honor the route-specific completion cap. Before that correction, local categories always used the global `LOCAL_ANSWER_MAX_COMPLETION_TOKENS=1000`.

Unchanged caps:

```text
CODE_DEBUGGING: 1000
CODE_GENERATION: 1000
MATHEMATICAL_REASONING: 400
SENTIMENT_CLASSIFICATION: 64
TEXT_SUMMARISATION: 1000
```

Result:

```text
exit_status: 0
elapsed_seconds: 472
results_json: present
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 317
completion_tokens: 1575
total_tokens: 1892
```

Comparison to prior Mode 1:

```text
prior Mode 1 elapsed_seconds: 460
256-cap experiment elapsed_seconds: 472
prior Fireworks total_tokens: 1758
256-cap experiment Fireworks total_tokens: 1892
```

Quality observations:

```text
T01c improved materially. The 256-token factual cap produced a real RAM/ROM answer instead of meta text.
T03 remained bad/risky. It still used SENTIMENT_CLASSIFICATION max_completion_tokens=64 and returned meta-reasoning.
T03b improved in this run despite still using the 64-token sentiment cap, but this appears unstable.
T05 regressed badly. NER at 256 local tokens truncated after "**Extracted Named Entities** | Entity".
```

Conclusion:

```text
FACTUAL_KNOWLEDGE=256 looks beneficial.
LOGICAL_DEDUCTIVE_REASONING=256 was not exercised by this public sample set.
NAMED_ENTITY_RECOGNITION=256 is too low for the observed local NER output style.
SENTIMENT_CLASSIFICATION=64 remains a likely quality risk.
```

## Follow-Up Sentiment 256 And NER 1000 Experiment

Date: 2026-07-14

Local image:

```text
amd-hackathon:version7-mode1-256-factual-sentiment-ner1000-local
```

Changes tested relative to the prior token-cap experiment:

```text
NAMED_ENTITY_RECOGNITION max_completion_tokens: 256 -> 1000
SENTIMENT_CLASSIFICATION max_completion_tokens: 64 -> 256
```

Retained from the prior experiment:

```text
FACTUAL_KNOWLEDGE max_completion_tokens: 256
LOGICAL_DEDUCTIVE_REASONING max_completion_tokens: 256
Mode 1 post-classification parallel scheduler
```

Result:

```text
exit_status: 0
elapsed_seconds: 427
results_json: present
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 317
completion_tokens: 1617
total_tokens: 1934
```

Comparison:

```text
Mode 1 baseline elapsed_seconds: 460
Mode 1 baseline Fireworks total_tokens: 1758

256-cap experiment elapsed_seconds: 472
256-cap experiment Fireworks total_tokens: 1892

Sentiment 256 / NER 1000 elapsed_seconds: 427
Sentiment 256 / NER 1000 Fireworks total_tokens: 1934
```

Quality observations:

```text
T03 improved. Sentiment 256 produced a complete one-sentence answer.
T03b improved. Sentiment 256 produced a complete one-sentence answer.
T05 recovered. NER 1000 produced all five expected named entities with labels.
T01c remained improved compared with the 64-token baseline, but the answer still appears to stop after RAM details before fully explaining ROM usage; treat as residual risk.
T04b remains borderline because the first bullet says remote work reshapes operations but does not explicitly state the expected benefit.
```

Conclusion:

```text
SENTIMENT_CLASSIFICATION=256 is materially better than 64.
NAMED_ENTITY_RECOGNITION should remain 1000 for the local NER path.
FACTUAL_KNOWLEDGE=256 is better than 64, but may still need answer-shaping or a slightly different cap/prompt to reliably cover both RAM and ROM.
This is the best runtime result observed so far on the public 10-task set: 427 seconds with valid results.json.
```

## Fixed Answer Wrapper Experiment

Date: 2026-07-14

Local image:

```text
amd-hackathon:version7-mode1-wrappers-local
```

Changes tested:

```text
Mode 1 post-classification parallel scheduler
FACTUAL_KNOWLEDGE max_completion_tokens: 256
LOGICAL_DEDUCTIVE_REASONING max_completion_tokens: 256
SENTIMENT_CLASSIFICATION max_completion_tokens: 256
NAMED_ENTITY_RECOGNITION max_completion_tokens: 1000
fixed route-specific answer wrappers baked into version7.py
```

The wrappers are fixed runtime constants, not interactive/manual prompt edits.

Result:

```text
exit_status: 0
elapsed_seconds: 423
results_json: present
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 458
completion_tokens: 2059
total_tokens: 2517
```

Comparison to the prior best no-wrapper run:

```text
prior best elapsed_seconds: 427
wrapper elapsed_seconds: 423

prior best Fireworks total_tokens: 1934
wrapper Fireworks total_tokens: 2517

prior best results.json bytes: 5429
wrapper results.json bytes: 2704
```

Quality observations:

```text
T01c improved. It now cleanly covers RAM and ROM.
T03 remained clean.
T03b remained clean.
T04 remained good.
T04b improved and now explicitly covers benefits, challenges, and organisational response.
T05 improved to concise labeled entities.
T01b regressed badly. It was classified as CODE_GENERATION, received the code-generation wrapper, consumed the full 1000 completion-token cap, and returned a truncated answer.
```

Conclusion:

```text
Fixed wrappers improve answer shape for most categories.
They increased judged Fireworks tokens substantially on this sample: +583 total tokens.
The CODE_GENERATION wrapper is dangerous when the classifier misroutes factual explanation tasks into CODE_GENERATION.
Do not promote the wrapper set as tested without changing the CODE_GENERATION wrapper to be category-agnostic or improving classification for T01/T01b-style prompts.
```

## Local-Only Answer Wrapper Experiment

Date: 2026-07-14

Local image:

```text
amd-hackathon:version7-mode1-local-wrappers-only
```

Changes tested:

```text
Fireworks-routed tasks use the raw task prompt.
Local Ollama-routed tasks use fixed category wrappers.
Mode 1 post-classification parallel scheduler.
FACTUAL_KNOWLEDGE max_completion_tokens: 256
LOGICAL_DEDUCTIVE_REASONING max_completion_tokens: 256
SENTIMENT_CLASSIFICATION max_completion_tokens: 256
NAMED_ENTITY_RECOGNITION max_completion_tokens: 1000
```

Result:

```text
exit_status: 0
elapsed_seconds: 498
results_json: present
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 317
completion_tokens: 1717
total_tokens: 2034
```

Comparison:

```text
prior best no-wrapper total_tokens: 1934
local-only wrapper total_tokens: 2034
all-wrapper total_tokens: 2517

prior best no-wrapper elapsed_seconds: 427
local-only wrapper elapsed_seconds: 498
all-wrapper elapsed_seconds: 423
```

Quality observations:

```text
T01b recovered compared with all-wrapper mode because Fireworks no longer receives the CODE_GENERATION wrapper.
T03 and T03b remained clean because sentiment cap remains 256.
T04b improved compared with no-wrapper mode and now covers benefits, challenges, and organisational response.
T05 stayed clean and concise.
T01c did not fully recover; without the factual Fireworks wrapper it still tends to spend the 256-token budget mostly on RAM and truncates before fully covering ROM.
```

Conclusion:

```text
Local-only wrappers are better than all-wrapper mode for token efficiency and avoid the T01b regression.
They improve local output shape, especially T04b and T05.
They do not solve the Fireworks factual-answer truncation risk for T01c.
This variant costs only +100 Fireworks tokens versus the prior no-wrapper best run, but is slower in this sample.
```

## Targeted Factual Fireworks And Local Wrapper Experiment

Date: 2026-07-14

Local image:

```text
amd-hackathon:version7-mode1-factual-local-wrappers
```

Changes tested:

```text
Fireworks-routed FACTUAL_KNOWLEDGE tasks use the fixed factual wrapper.
Other Fireworks-routed tasks use the raw task prompt.
Local Ollama-routed tasks use fixed category wrappers.
Mode 1 post-classification parallel scheduler.
FACTUAL_KNOWLEDGE max_completion_tokens: 256
LOGICAL_DEDUCTIVE_REASONING max_completion_tokens: 256
SENTIMENT_CLASSIFICATION max_completion_tokens: 256
NAMED_ENTITY_RECOGNITION max_completion_tokens: 1000
```

Result:

```text
exit_status: 0
elapsed_seconds: 450
results_json: present
classified: 10
routed: 10
remote_answered: 7
local_answered: 3
```

Fireworks token usage reported by the API:

```text
prompt_tokens: 342
completion_tokens: 1573
total_tokens: 1915
```

Comparison:

```text
prior best no-wrapper total_tokens: 1934
targeted factual/local wrapper total_tokens: 1915
local-only wrapper total_tokens: 2034
all-wrapper total_tokens: 2517

prior best no-wrapper elapsed_seconds: 427
targeted factual/local wrapper elapsed_seconds: 450
local-only wrapper elapsed_seconds: 498
all-wrapper elapsed_seconds: 423
```

Quality observations:

```text
T01b remained good because CODE_GENERATION Fireworks prompts stay raw.
T01c improved and now covers both RAM and ROM.
T03 and T03b remained clean because sentiment cap remains 256.
T04b remained improved due local summarisation wrapper.
T05 remained clean and concise due local NER wrapper.
```

Conclusion:

```text
This is the best observed variant on the public 10-task set.
It improves known weak outputs while slightly reducing Fireworks token usage versus the prior no-wrapper best run.
The runtime remains under the 10-minute limit.
```

## Final Policy

Date: 2026-07-14

Promote the targeted factual/local wrapper variant as the final local candidate
policy.

Scheduler:

```text
Default mode: post_classification_parallel
Classify and route every task first.
Then start answer generation for all routed tasks.
Fireworks answer tasks run with bounded remote concurrency.
Local Ollama answer tasks run serially.
No local classification or local answer generation runs concurrently.
```

Completion caps:

```text
CODE_DEBUGGING:                  1000
CODE_GENERATION:                 1000
FACTUAL_KNOWLEDGE:               256
LOGICAL_DEDUCTIVE_REASONING:     256
MATHEMATICAL_REASONING:          400
NAMED_ENTITY_RECOGNITION:        1000
SENTIMENT_CLASSIFICATION:        256
TEXT_SUMMARISATION:              1000
```

Prompt policy:

```text
Wrappers are fixed constants in src/amd_hackathon_app/version7.py.
Wrappers are prepended to the single user message.
Wrappers are not system prompts.
Classifier prompts are separate and do not use answer wrappers.
```

Fireworks primary answer policy:

```text
FACTUAL_KNOWLEDGE uses the fixed factual wrapper.
CODE_GENERATION uses the raw official prompt.
LOGICAL_DEDUCTIVE_REASONING uses the raw official prompt.
MATHEMATICAL_REASONING uses the raw official prompt.
SENTIMENT_CLASSIFICATION uses the raw official prompt.
```

Local Ollama answer policy:

```text
CODE_DEBUGGING uses its fixed wrapper.
NAMED_ENTITY_RECOGNITION uses its fixed wrapper.
TEXT_SUMMARISATION uses its fixed wrapper.
Any Fireworks-primary category that falls back to local Ollama uses its fixed category wrapper.
```

Fallback policy:

```text
Fallback answer calls keep the original route category.
Fallback answer calls keep the same max_completion_tokens as the original route category.
Fallback answer calls use the same category prompt policy.
FACTUAL_KNOWLEDGE fallback to Minimax keeps the factual wrapper.
Local-primary categories that fall back to Fireworks keep their category wrapper.
Raw-primary Fireworks categories remain raw when falling back to another Fireworks model.
```

Final verification in the working tree:

```text
unit tests: 68 passed via PYTHONPATH=src python3 -m unittest discover -s tests
```

Publication note:

```text
The published image ghcr.io/hatikva/amd-hackathon-app:version7-production-429c37b remains the previously verified public image.
This final policy is documented for the next image built from the working tree.
```
