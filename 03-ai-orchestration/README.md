## Kestra AI Copilot vs ChatGPT
 
Same prompt given to both: "Create a Kestra flow that loads NYC taxi data from CSV to BigQuery."
 
### ChatGPT's Output
 
```yaml
id: nyc_taxi_csv_to_bigquery
namespace: company.team
variables:
  project_id: your-gcp-project
  bucket: your-gcs-bucket
  dataset: nyc_taxi
  table: yellow_tripdata
  csv_url: https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/yellow_tripdata_2023-01.csv.gz
tasks:
  - id: download_csv
    type: io.kestra.plugin.core.http.Download
    uri: "{{ vars.csv_url }}"
  - id: upload_to_gcs
    type: io.kestra.plugin.gcp.gcs.Upload
    from: "{{ outputs.download_csv.uri }}"
    bucket: "{{ vars.bucket }}"
    name: "yellow_tripdata_2023_01.csv.gz"
  - id: load_to_bigquery
    type: io.kestra.plugin.gcp.bigquery.LoadFromGcs
    from:
      - "gs://{{ vars.bucket }}/yellow_tripdata_2023_01.csv.gz"
    destinationTable: "{{ vars.project_id }}.{{ vars.dataset }}.{{ vars.table }}"
    format: CSV
    compression: GZIP
    autodetect: true
    createDisposition: CREATE_IF_NEEDED
    writeDisposition: WRITE_TRUNCATE
    csvOptions:
      skipLeadingRows: 1
      allowQuotedNewLines: true
```
 
Looks fine on the surface, but it uses a task type that does not exist in Kestra: `io.kestra.plugin.gcp.bigquery.LoadFromGcs`. Made up name. This flow would fail if you tried to run it.
 
### Kestra AI Copilot's Output
 
```yaml
id: jaguar_273629
namespace: company.team
tasks:
  - id: download-nyc-taxi-data
    type: io.kestra.plugin.core.http.Download
    uri: "https://huggingface.co/datasets/kestra/datasets/raw/main/csv/orders.csv"
    saveAs: nyc_taxi_data.csv
  - id: load-nyc-taxi-data-to-bigquery
    type: io.kestra.plugin.gcp.bigquery.Load
    from: "{{ outputs['download-nyc-taxi-data'].uri }}"
    destinationTable: "my_project.my_dataset.nyc_taxi_data"
    format: CSV
    csvOptions:
      skipLeadingRows: 1
      allowJaggedRows: true
      allowQuotedNewLines: true
    # projectId: "your-gcp-project-id"
    # serviceAccount: "{{ secret('GCP_SERVICE_ACCOUNT') }}"
```
 
Simpler flow, but every task type and property is real. `io.kestra.plugin.gcp.bigquery.Load` actually exists, and the properties used match the real plugin schema.
 
### Why Copilot Won
 
Kestra's Copilot has access to Kestra's actual, current plugin documentation. It knows which plugins exist and what properties they take.
 
ChatGPT is working off general training data, so when it doesn't know the exact plugin name, it guesses one that sounds right. That's how `LoadFromGcs` got invented.
 
Same story either way: Copilot generated a working flow, ChatGPT generated one that would fail on the first task.

## RAG vs No RAG
 
Ran `1_chat_without_rag.yaml` and `2_chat_with_rag.yaml`, both asking about Kestra 1.1 features.
 
### Without RAG
 
Listed things like a plugin marketplace, OAuth2/JWT auth, and audit logs. None of these are actually Kestra 1.1 features. Some aren't Kestra features at all, others were added in different versions. The model had no real data to work from, so it filled in the answer using patterns from training data. Sounds confident, isn't accurate.
 
### With RAG
 
Listed real 1.1 features: new UI filters, a no code dashboard editor, multi agent AI systems, "Fix with AI," the Human Task feature, better air gapped support, and new plugins. This matches the actual release notes because the model pulled from retrieved documentation instead of guessing.
 
### The Point
 
Without retrieved context, the model guesses and produces answers that sound plausible but are wrong. With retrieved context, the model reports what's actually in the documentation. This is the difference RAG makes: it grounds the answer in real, current information instead of relying on what the model happened to learn during training.

## Token Usage, Short Summary
 
Ran `4_simple_agent.yaml` with `summary_length = short`, other inputs left as default. Checked the token usage logged by the `log_token_usage` task.
 
Multilingual Agent: 282 input tokens, 91 output tokens, 373 total.
English Brevity Agent: 106 input tokens, 46 output tokens, 152 total.
 
Output tokens for the multilingual agent landed in the 60 to 100 range. Worth tracking this kind of thing since token counts map directly to cost, and comparing agents side by side shows which prompts are running lean and which aren't.

## Token Usage, Long Summary
 
Ran the same flow again with `summary_length = long`.
 
Multilingual Agent: 282 input tokens, 202 output tokens, 484 total.
English Brevity Agent: 217 input tokens, 48 output tokens, 265 total.
 
Multilingual agent output tokens went from 91 (short) to 202 (long), about 2.2x more. That puts it in the 2 to 5x range, not a huge jump, but a real one. Makes sense since a longer summary just needs more words to say more, the cost scales with the length you ask for.

## Modifying a Flow
 
Changed the `english_brevity` task prompt from asking for exactly 1 sentence to asking for exactly 3 sentences. Ran it with `summary_length = long`.
 
English Brevity Agent: 190 input tokens, 87 output tokens, 277 total.
 
Original 1 sentence version (also long) used 48 output tokens. New 3 sentence version used 87. That's about 1.8x more, closest to the 2 to 4x range. Asking for more sentences in the prompt directly increases how much the model writes back, which increases the token count and the cost.