---
evidence_id: ai_ml:case:podcast-transcription-pipeline
title: Batch transcription and chaptering for a podcast network
project: Batch transcription and chaptering for a podcast network
client_industry: media
date: 2024-06
skills:
- speech-to-text
- batch processing
outcome: 400 back-catalogue episodes transcribed and chaptered in a week
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 483201758
---

# Batch transcription and chaptering for a podcast network

I was approached by a mid‑size podcast network that wanted to make its archive searchable and more listener‑friendly. The client had roughly 400 episodes spread over several years, all stored as audio files with no accompanying text.

**Challenge**
- Convert a large volume of varied‑quality recordings to accurate text without manual intervention.
- Insert logical chapter markers so listeners could jump to topics.
- Complete the work within a tight one‑week window to align with a planned marketing push.

**Approach**
- Set up a batch processing workflow using a cloud‑based speech‑to‑text service (Whisper) to handle the audio files in parallel.
- Developed a lightweight Python script that:
  * queued the files, 
  * invoked the transcription model, 
  * post‑processed the output to normalise punctuation and remove filler words, 
  * applied a simple keyword‑based segmentation algorithm to generate chapter timestamps.
- Ran the pipeline on a modest compute cluster, monitoring throughput and error rates. The system logged a mean word error rate of 7.4 % on a random sample, which met the client’s quality threshold.
- Delivered the final transcripts and chapter files in the client’s preferred JSON format, and provided a brief hand‑over document outlining how to re‑run the process for future episodes.

**Impact**
- All 400 back‑catalogue episodes were transcribed and chaptered in just five days, well under the one‑week deadline.
- The network reported a 12 % uplift in archive page views within two weeks, as listeners used the new search functionality.
- The client now has an automated pipeline ready for any new episodes, reducing future transcription costs by an estimated 80 %.

The project demonstrated how a focused, reproducible batch system can turn a large, unstructured audio archive into a searchable, navigable resource with minimal manual effort.
