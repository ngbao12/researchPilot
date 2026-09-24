# ResearchPilot — measured execution report

Structural citation validity and coverage do **not** measure factual correctness or semantic support. Undefined ratios are N/A. Gold annotations remain unverified unless independently audited. VLM: **not evaluated**.

| Mode | Model | N | Citation validity | Recall | Correctness scored |
|---|---|---:|---|---|---|
| table-rag | extractive/quotes-v1 | 12 | 14/14 | 7/18 | N/A (0 denominator) |
| text-rag | extractive/quotes-v1 | 12 | 14/14 | 7/18 | N/A (0 denominator) |

Full numerator/denominator, per-category, per-modality, held-out results, latency p50/p95, usage, configs and per-question decisions are in `evaluation_metrics.json`. Latency includes retrieval and generation, excludes initial model/index loading. Offline token counts are estimates; API cost is not measured.

## Failure cases (up to five observed cases)

### table-rag / Q01
What is the key architectural innovation in MobileNets that reduces computational cost?
- Answer: Extracted evidence: “The second hyper-parameter to reduce the computational cost of a neural network is a resolution multiplier ρ . We ap-” [P01, p.4, ev-P01-p4-t20-c0].
- Expected source references (unverified gold): P01 p.1, P01 p.2
- Retrieved: ev-P01-p4-t20-c0, ev-P01-p4-t16-c0, ev-P01-p4-t18-c0, ev-P01-p8-t3-c0, ev-P01-p3-t3-c0
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### table-rag / Q02
What is the compound scaling method proposed in EfficientNet, and how does it differ from single-dimension scaling?
- Answer: Extracted evidence: “ods for the same EfficientNet-B0 baseline network. In general, all scaling methods improve accuracy with the cost of more FLOPS, but our compound scaling method can further improve accuracy, by up to 2.5%, than other singledimension scaling methods, suggesting the importance of our proposed compound scaling.” [P02, p.8, ev-P02-p8-t31-c0].
- Expected source references (unverified gold): P02 p.1, P02 p.3
- Retrieved: ev-P02-p8-t31-c0, ev-P02-p5-t25-c0, ev-P02-p8-t13-c0, ev-P02-p5-t18-c0, ev-P02-p3-t4-c0
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### table-rag / Q03
What ImageNet top-1 accuracy does EfficientNet-B7 achieve, and how does it compare to the previous best?
- Answer: Extracted evidence: “To go even further, we use neural architecture search to design a new baseline network and scale it up to obtain a family of models, called EfficientNets , which achieve much better accuracy and efficiency than previous ConvNets. In particular, our EfficientNet-B7 achieves state-of-the-art 84.3% top-1 accuracy on ImageNet, while being 8.4x smaller and 6.1x faster on inference than the best existing ConvNet. Our EfficientNets also transfer well and achieve state-of-the-art accuracy on CIFAR-100 (91.7%), Flowers (98.8%), and 3 other transfer learning datasets, with an order of magnitude fewer parameters. Source code is at https: //github.com/tensorflow/tpu/tree/ master/models/official/efficien” [P02, p.1, ev-P02-p1-t4-c0].
- Expected source references (unverified gold): P02 p.6, P02 p.6
- Retrieved: ev-P02-p1-t4-c0, ev-P02-p2-t14-c1, ev-P02-p7-t66-c0, ev-P02-p7-t3-c0, ev-P02-p7-t68-c0
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### table-rag / Q05
Compare the scaling approaches of MobileNets and EfficientNet for achieving different accuracy-efficiency tradeoffs.
- Answer: Extracted evidence: “In this section, we will formulate the scaling problem, study different approaches, and propose our new scaling method.” [P02, p.3, ev-P02-p3-t4-c0].
- Expected source references (unverified gold): P01 p.4, P02 p.3
- Retrieved: ev-P02-p3-t4-c0, ev-P02-p8-t13-c0, ev-P02-p8-t31-c0, ev-P02-p5-t25-c0, ev-P02-p7-t66-c0
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### table-rag / Q06
What training data augmentation techniques are common across all four papers?
- Answer: Extracted evidence: “parameters as can be seen in Table 2 . Nearly all of the additional parameters are in the fully connected layer. MobileNet models were trained in TensorFlow [ 1 ] using RMSprop [ 33 ] with asynchronous gradient descent similar to Inception V3 [ 31 ]. However, contrary to training large models we use less regularization and data augmentation techniques because small models have less trouble with overfitting. When training MobileNets we do not use side heads or label smoothing and additionally reduce the amount image of distortions by limiting the size of small crops that are used in large Inception training [ 31 ]. Additionally, we found that it was important to put very little or no w” [P01, p.4, ev-P01-p4-t10-c1].
Extracted evidence: “To compute maps of the attention from the output token to the input space (Figures 6 and 14), we used Attention Rollout (Abnar & Zuidema, 2020). Briefly, we averaged attention weights of ViTL/16 across all heads and then recursively multiplied the weight matrices of all layers. This accounts for the mixing of attention across tokens through all layers.” [P03, p.20, ev-P03-p20-t37-c0].
- Expected source references (unverified gold): unanswerable
- Retrieved: ev-P01-p4-t10-c1, ev-P03-p20-t37-c0, ev-P02-p9-t16-c0, ev-P03-p5-t7-c0, ev-P01-p4-t10-c2
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

## Human review
Score review_template.jsonl blind to mode; keep blind_key.json separate from reviewers. Map review_id back to run_id/question_id, save JSONL judgments, then pass --judgments. Use correctness=1 only when all required facts match and no contradicted facts are added. Record annotator and rationale. Semantic support requires checking each cited claim against the source.
