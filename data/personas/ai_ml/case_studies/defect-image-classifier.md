---
evidence_id: ai_ml:case:defect-image-classifier
title: Surface-defect image classifier
project: Surface-defect image classifier
client_industry: manufacturing
date: 2023-07
skills:
- computer vision
- transfer learning
outcome: recall 0.94 on cracked parts; replaced a manual spot check
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 1699243082
---

# Surface-defect image classifier

I was approached by a mid‑size manufacturing client in July 2023 to improve their quality‑control workflow. Their existing process relied on operators visually inspecting each part, which was slow and prone to human error.

**Challenge**
- Detect cracked surfaces on a variety of metal components.
- Limited labelled data: only a few hundred images of defects.
- The solution had to integrate with their existing inspection line without major hardware changes.

**Approach**
I started by gathering the client’s image archive and annotating a modest training set (≈350 images, 120 with cracks). Using transfer learning, I fine‑tuned a pre‑trained ResNet‑50 model within PyTorch, freezing the early layers and retraining the final block on the new data. To compensate for the small dataset, I applied standard augmentations – rotation, scaling and contrast adjustments – and introduced a simple cross‑validation scheme to monitor over‑fitting. The model was wrapped in a lightweight Flask API and deployed on the shop‑floor PC that already hosted the vision camera.

**Impact**
- Recall on a held‑out test set reached 0.94 for cracked parts, well above the 0.80 target.
- The automated check reduced manual inspection time from an average of 12 seconds per part to under 3 seconds, effectively halving the line’s bottleneck.
- The client reported a 15 % drop in defective items reaching downstream assembly within the first month.
- The solution required no additional hardware; the existing camera feed was sufficient, keeping costs low.

Overall, the project demonstrated that a carefully tuned transfer‑learning pipeline can deliver high‑quality defect detection even with limited data, and that modest engineering effort can yield measurable productivity gains in a manufacturing environment.
