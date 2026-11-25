# TruthLens AI — Project Report

## 1. Problem

Online misinformation can spread rapidly across low-trust and high-volume
channels. TruthLens is a decision-support prototype that helps readers examine
a headline and article text, inspect learned language signals, and consult
independent fact-check reviews. It is not an autonomous adjudication system.

## 2. Objectives

- Accept and validate news submissions.
- Preserve submissions with a configurable database provider.
- Compare text with a documented benchmark dataset.
- Display confidence and explainable model associations.
- Separate model predictions from independent fact-check evidence.
- Provide a responsive, accessible web interface.
- Test, package, and document the complete system.

## 3. System architecture

- React + TypeScript frontend.
- FastAPI REST API and OpenAPI documentation.
- SQLite for local development and Supabase/PostgreSQL for production.
- TF-IDF + Logistic Regression traditional NLP baseline.
- Optional fine-tuned DistilBERT transformer.
- Google Fact Check Tools API integration.
- Docker packaging for frontend and API deployment.

## 4. Dataset

The implemented dataset is LIAR, the six-class benchmark released for
*“Liar, Liar Pants on Fire”* (ACL 2017). The README permits research use and
states that original sources retain copyright and that the release is provided
as-is. The project prepares the supplied train/validation/test partitions and
uses statement text only.

The six label classes are not objective machine-generated truth labels. Their
scope is limited to the benchmark source, time, topics, and labeling process.
All external users are warned to consult independent evidence.

## 5. Traditional model results

The first implementation uses unigrams/bigrams, sublinear TF-IDF, and balanced
Logistic Regression. It achieved:

- Test accuracy: 0.248
- Test macro-F1: 0.246

These results show that the baseline is a weak but reproducible comparison
model, not a sufficiently reliable misinformation adjudicator for deployment.
No result is presented as a probability that a claim is true.

## 6. Transformer status

The transformer script fine-tunes `distilbert-base-uncased` for the six LIAR
labels. Local CPU fine-tuning proved impractical for the initial 10,240-row
training set. The project therefore retains the traditional model as the
working default and the DistilBERT path as an optional, GPU-oriented pipeline
pending held-out evaluation.

## 7. Explainability

The traditional model reports the predicted benchmark label, maximum class
probability, and TF-IDF token contributions. Each response explicitly states
that these features are associations rather than evidence. Transformer
attributions are implemented with an input-gradient approximation and similarly
marked as approximate.

## 8. Limitations

- LIAR contains short political statements, not full articles.
- Fact-check coverage is incomplete and API-dependent.
- SQLite is suitable for local development, not production concurrency.
- Cloud Supabase credentials and a live fact-check key were not available.
- The transformer is not yet fine-tuned or validated.
- No authentication or legal/privacy review should be assumed complete.

## 9. Future improvements

- Fine-tune and evaluate transformer or domain-specific models on GPU.
- Add retrieval from reputable publishers and dated source documents.
- Calibrate confidence and implement abstention thresholds.
- Add user authentication and per-account authorization.
- Add abuse protection, audit logging, and rate limiting.
- Add end-to-end browser tests and CI/CD.
- Deploy API and frontend with production secrets and managed database.
