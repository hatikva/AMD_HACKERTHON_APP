# Categorization Risk

Category classification is one of the highest-risk control-plane functions in the Version 5 routing path.

A miscategorization can route a task to the wrong model authority. In particular, a coding task misclassified into math, logical, or factual work could be routed to `nemotron-3-nano:4b` or `minimax-m3` despite weak current code generation and code debugging evidence.

Category classification must be tested and reviewed before authority promotion. Benchmark evaluator metadata must remain withheld from model-visible official-shape tasks: the categorizer receives only records containing `task_id` and `prompt`, and evaluator-only expected categories are joined later by `task_id`.

The Version 5 analytics artifact records categorization accuracy, a confusion matrix, precision and recall, and miscategorized task IDs. That artifact is reviewed evidence only; it does not mutate runtime authorization and does not certify local jurisdictions.
