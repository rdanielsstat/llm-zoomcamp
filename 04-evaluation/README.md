# Module 4: Search Evaluation

This mini-project compares keyword, vector, and hybrid search on the course lessons. An earlier module built all three but left the question of which one is best. Here I answer that by measuring instead of guessing.

## What I did

1. Loaded the 72 lesson pages from the course repo at commit `8c1834d`.
2. Generated ground truth questions with an LLM: for each page, ask the model to write 5 questions the page answers, then label each question with its source page. I generated a sample for the first 3 pages and used the prepared `ground-truth.csv` (360 questions) for the rest.
3. Chunked the pages (`size=2000`, `step=1000`, giving 295 chunks) and rebuilt text, vector, and hybrid search over them, all keyed on `filename`.
4. Evaluated each search method against the ground truth using Hit Rate and MRR.
5. Tuned the RRF `k` constant for hybrid search.

## Ground truth

To measure search, you need a set of questions where you already know the correct answer. Each ground truth record pairs a question with the filename of the page that answers it. The LLM writes questions in different words from the page on purpose, since copying the page's phrasing would make retrieval too easy and would not reflect how people actually ask things.

## Metrics

A result counts as a hit when a returned chunk's `filename` matches the question's `filename`.

**Hit Rate** (Recall@k) is the fraction of questions where the correct page shows up anywhere in the top results. It tells you whether search found the page, but not where.

**MRR** (Mean Reciprocal Rank) also accounts for position. If the correct page is first, the score is 1.0; if second, 0.5; if third, 0.33, and so on. A method that ranks the right page higher scores better, even when both methods eventually find it.

The `evaluate` function runs any search function over the whole ground truth and returns both numbers. Because the ground truth stays fixed, you can change one setting, re-run `evaluate`, and see whether the metric moves.

## Search methods

**Text search** matches on shared words. Fast, but misses pages that answer the question in different vocabulary.

**Vector search** embeds the query and chunks with a local ONNX model (`all-MiniLM-L6-v2`) and ranks by cosine similarity. It catches semantic matches that keyword search misses. One example: a question generated from the intro page lands the intro page at the top for vector search but not for text search.

**Hybrid search** runs both and merges the two ranked lists with Reciprocal Rank Fusion (RRF). RRF scores each result by `1 / (k + rank)` summed across the lists, so a page ranked well by both methods rises to the top.

## Tuning k

The `k` constant in RRF controls how much the top ranks matter. A smaller `k` widens the gap between positions, so being first counts for more. The RRF paper defaults to 60, but the best value depends on the data. Testing `k` values of 1, 50, 100, and 200, the smallest value gave the best MRR. The three larger values tied, because once `k` is large relative to the rank positions the differences between them wash out.

## Using this

The same `evaluate` function measures any change to search: field boosts in keyword search, a different embedding model, the RRF `k`, or the number of results returned. Change a setting, re-run, and compare.

## Files

- `evaluation.ipynb`: the notebook with all steps
- `evaluation_utils.py`: helpers for structured LLM output, usage tracking, and parallel processing
- `embedder.py`: the local ONNX embedding model wrapper
- `ground-truth.csv`: the 360 labeled questions
