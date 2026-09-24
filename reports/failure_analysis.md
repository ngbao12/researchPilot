# Failure analysis — offline run 2026-09-24

These five diagnoses were written by AI after inspecting saved predictions and local source pages. They are not independent human rubric scores. Run: `results/final-20260924`. All gold questions remain unverified.

## Q01: Wrong focus despite valid citation
- Mode: `text-rag`
- Question: What is the key architectural innovation in MobileNets that reduces computational cost?
- Observed output: Extracted evidence: “The second hyper-parameter to reduce the computational cost of a neural network is a resolution multiplier ρ . We ap-” [P01, p.4, ev-P01-p4-t20-c0].
- Diagnosis: The selected passage describes the resolution multiplier, while the question asks for the architectural innovation: depthwise separable convolutions (P01 pages 1–2). Lexical overlap on computational cost outranked the definition. Structural validity cannot detect this semantic mismatch.
- Gold source pages: P01 p.1, P01 p.2
- Retrieved `ev-P01-p4-t20-c0` (P01 p.4, score 0.218): The second hyper-parameter to reduce the computational cost of a neural network is a resolution multiplier  ρ . We ap-…
- Retrieved `ev-P01-p4-t16-c0` (P01 p.4, score 0.145): and width multiplier  α , the number of input channels  M  becomes  αM  and the number of output channels  N  becomes αN . The computational cost of a depthwise separable convolution with width multip…

## Q04: A chunk loses the preceding explanation
- Mode: `text-rag`
- Question: How does the Vision Transformer (ViT) handle variable-resolution images during inference?
- Observed output: Extracted evidence: “this resolution adjustment and patch extraction are the only points at which an inductive bias about the 2D structure of the images is manually injected into the Vision Transformer.” [P03, p.4, ev-P03-p4-t9-c1].
- Diagnosis: The selected fragment refers to resolution adjustment but omits the 2D position-embedding interpolation stated earlier on P03 page 4. Page-level recall credits the correct page even when the delivered excerpt lacks the required fact. Chunk context or a semantic generator is needed.
- Gold source pages: P03 p.4
- Retrieved `ev-P03-p4-t9-c1` (P03 p.4, score 0.323): this resolution adjustment and patch extraction are the only points at which an inductive bias about the 2D structure of the images is manually injected into the Vision Transformer.…
- Retrieved `ev-P03-p15-cap5-c0` (P03 p.15, score 0.229): Table 5: Top1 accuracy (in %) of Vision Transformer on various datasets when pre-trained on Im- ageNet, ImageNet-21k or JFT300M. These values correspond to Figure 3 in the main text. Models are fine-t…

## Q06: Partial evidence does not establish a claim about all papers
- Mode: `text-rag`
- Question: What training data augmentation techniques are common across all four papers?
- Observed output: Extracted evidence: “parameters as can be seen in Table 2 . Nearly all of the additional parameters are in the fully connected layer. MobileNet models were trained in TensorFlow [ 1 ] using RMSprop [ 33 ] with asynchronous gradient descent similar to Inception V3 [ 31 ]. However, contrary to trainin…
- Diagnosis: The draft question asks what is common to all four papers. Retrieved training paragraphs from a subset cannot support a universal claim; the offline quotation generator still emits excerpts. This is a missed abstention under the draft annotation, which itself needs human verification.
- Gold source pages: 
- Retrieved `ev-P01-p4-t10-c1` (P01 p.4, score 0.217): parameters as can be seen in Table  2 . Nearly all of the additional parameters are in the fully connected layer. MobileNet models were trained in TensorFlow [ 1 ] using RMSprop [ 33 ] with asynchrono…
- Retrieved `ev-P03-p20-t37-c0` (P03 p.20, score 0.207): To compute maps of the attention from the output token to the input space (Figures 6 and 14), we used Attention Rollout (Abnar & Zuidema, 2020). Briefly, we averaged attention weights of ViTL/16 acros…

## Q08: Table retrieval misses the requested GPU labels
- Mode: `table-rag`
- Question: Which GPU devices are used for EfficientViT latency and throughput comparisons in Table 2?
- Observed output: Extracted evidence: “Latency Measurement. We measure the mobile latency on Qualcomm Snapdragon 8Gen1 CPU with TensorflowLite 3 , batch size 1 and fp32. We use TensorRT 4 and fp16 to measure the latency on edge GPU and cloud GPU. The data transfer time is included in the reported latency/throughput r…
- Diagnosis: The selected text describes a mobile CPU and generic edge/cloud GPU measurement protocol on P04 page 5, whereas the question targets Table 2 on page 6 (Nano, Orin, A100). Table extraction is incomplete, and a valid quote from a related methods paragraph is insufficient.
- Gold source pages: P04 p.6
- Retrieved `ev-P04-p5-t41-c0` (P04 p.5, score 0.330): Latency Measurement. We measure the mobile latency on Qualcomm Snapdragon 8Gen1 CPU with TensorflowLite 3 , batch size 1 and fp32. We use TensorRT 4   and fp16 to measure the latency on edge GPU and c…
- Retrieved `ev-P04-p2-cap34-c0` (P04 p.2, score 0.306): Figure 1: Latency/Throughput vs. Performance. All performance results are obtained with the single model and single- scale inference. The GPU latency/throughput results are obtained on one edge GPU (J…

## Q09: Conservative similarity threshold rejects potentially useful context
- Mode: `text-rag`
- Question: What is the relationship between patch size and accuracy in ViT according to the ablation results?
- Observed output: insufficient_evidence
- Diagnosis: The pipeline abstains on the draft figure question. Gold references point to P03 page 7 Figure 3 and the patch-size explanation on page 5. A low cosine score is a heuristic; abstention here does not prove the PDF lacks evidence. Tune thresholds on a separate development set, then evaluate once on fresh held-out questions.
- Gold source pages: P03 p.7, P03 p.5
- Retrieved `ev-P03-p5-t5-c0` (P03 p.5, score 0.331): Model Variants.  We base ViT configurations on those used for BERT (Devlin et al., 2019), as summarized in Table 1. The “Base” and “Large” models are directly adopted from BERT and we add the larger “…
- Retrieved `ev-P03-p17-cap15-c0` (P03 p.17, score 0.277): Table 8: Results of the ablation study on positional embeddings with ViT-B/16 model evaluated on ImageNet 5-shot linear.…

