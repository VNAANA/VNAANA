# Genre Classification

We use a fine-tuned Dutch RobBERT V2 model to predict genres for news Stories in VNAANA.

The classifier takes a Story's **title, optional summary and context** and returns up to three genres with scores. It selects genres with scores of at least **0.60**.

### Current status

So far, we have:

- Trained and tested our RobBERT V2 model.
- Built `GenreClassificationService` for predictions.
- Built `GenreClassificationTagAdapter` to match predictions with database Tag IDs.
- Tested the complete process using three draft Stories in Supabase, including saving their tags and scores.

The standalone batch is ready for explicit Story IDs. Automatic pipeline classification is disabled by default.

## 1. Set up the model

The trained model is stored in Google Drive instead of GitHub because the checkpoint is quite large (around 500 MB).

**Download the original PyTorch model:**

[RobBERT V2 – Google Drive](https://drive.google.com/drive/folders/1XvSggvRrIqW7DzrD2nZp36VhplDUowl3?usp=drive_link)

Download the complete folder and extract it somewhere on your laptop, for example:

`C:\Models\nl_news_classifier_v2`

Keep the original files together, including `model.safetensors`, `config.json` and the tokenizer files.

We also experimented with a smaller ONNX version, but the current backend service uses the original PyTorch model.

### Install dependencies

From the project root, install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

The classifier uses PyTorch, Transformers and Safetensors. Their tested versions have been added to the project's requirements.

### Configure the model path

In the VS Code PowerShell terminal:

```powershell
$env:GENRE_CLASSIFICATION_MODEL_PATH = "C:\Models\nl_news_classifier_v2"
$env:GENRE_CLASSIFICATION_DEVICE = "cpu"
```

Change the path to wherever you downloaded the model.

Both manual runners use `GENRE_CLASSIFICATION_DEVICE`. If you pass
`--device cpu` or `--device cuda`, that command-line value takes priority.

You can also add these settings to your local `Backend/.env` file:

```ini
GENRE_CLASSIFICATION_MODEL_PATH=C:\Models\nl_news_classifier_v2
GENRE_CLASSIFICATION_DEVICE=cpu
```

The model runs locally, so no API key is needed. Only the machine running the classification backend needs to have the model downloaded.

## 2. Test the classifier

To check whether the model works on your laptop, run this from the repository root:

```powershell
python -m tests.backend.manual.genre_classification_inference
```

This runs predictions on three example Stories and prints their genres and scores.

It does **not** connect to Supabase or change any database records.

## 3. How to use it with Story generation

The main files are:

| File | Purpose |
|---|---|
| `Logic/genre_classification_service.py` | Loads RobBERT and predicts genres |
| `Logic/genre_classification_tag_adapter.py` | Matches predicted genres with database Tag IDs |
| `StoryService.add_genre_tags_if_current()` | Saves tags and relevance scores if the Story is still current and untagged |

`classify_grouped_stories()` in `jobs/classify_grouped_stories.py` accepts explicit IDs of already committed Stories and loads the finalized RobBERT V2 model once per batch. It processes only untagged Stories and skips empty predictions or Story inputs that changed during inference. It saves Tag IDs and relevance scores in `story_tags` through the existing services and repositories.

`run_news_pipeline.py` reuses this batch after Story Grouping commits. It passes only the Stories touched by that grouping run. Predictions are saved only when a Story is still untagged and its title, summary and context are unchanged. A failure for one Story does not stop classification of the other Stories or completion of the news pipeline.

The automatic step is disabled by default. It can be enabled in the target runtime with:

```ini
GENRE_CLASSIFICATION_PIPELINE_ENABLED=true
```

## 4. Things still to finish

**Azure setup:** The Azure job still needs access to the finalized checkpoint and the correct model path. Deployment and scheduled execution still need validation.

Keep scheduled classification disabled until the Azure checkpoint setup, deployment validation.
