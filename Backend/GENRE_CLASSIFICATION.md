# Genre Classification

We use a fine-tuned Dutch RobBERT V2 model to predict genres for news Stories in VNAANA.

The classifier takes a Story's **title, summary and context** and returns up to three genres with scores. We currently use a threshold of **0.60**, so only genres above this threshold are selected.

### Current status

So far, we have:

- Trained and tested our RobBERT V2 model.
- Built `GenreClassificationService` for predictions.
- Built `GenreClassificationTagAdapter` to match predictions with database Tag IDs.
- Tested the complete process using three draft Stories in Supabase, including saving their tags and scores.

**Important:** The classifier works, but it is not automatically connected to Story generation yet. This still needs to be done when the Story-generation algorithm is ready.

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
python -m Backend.tests.manual.genre_classification_inference
```

This runs predictions on three example Stories and prints their genres and scores.

It does **not** connect to Supabase or change any database records.

## 3. How to use it with Story generation

The main files are:

| File | Purpose |
|---|---|
| `Logic/genre_classification_service.py` | Loads RobBERT and predicts genres |
| `Logic/genre_classification_tag_adapter.py` | Matches predicted genres with database Tag IDs |
| `StoryService.set_tags()` | Saves the selected tags and relevance scores |

The idea is to classify a Story **after the Story-generation algorithm has finished creating its title, summary and context**.

The workflow should be:

1. Story generation creates a draft Story.
2. RobBERT predicts the genres from its title, summary and context.
3. The tag adapter finds the matching Tag IDs.
4. `StoryService.set_tags()` saves the tags and their scores in `story_tags`.

For example, after the services have been initialized:

```python
predictions = classifier.classify(
    title=story.title,
    summary=story.summary,
    context=story.context,
)

tags = GenreClassificationTagAdapter(
    tag_repository
).to_story_tags(predictions)

story_service.set_tags(story.id, tags)
```

This is an example of how to connect the components, **not an automatic integration already implemented in the backend**.

A few things to keep in mind:

- Load the classifier once and reuse it for multiple Stories, rather than loading the model every time.
- Only save predictions when the newly created Story has no existing tags. `set_tags()` replaces existing assignments.
- The classifier should be called from the Story-generation workflow, not directly inside the general `StoryService.create_story()` method.

We will need to coordinate the exact integration with the teammate working on Story generation.

## 4. Things still to finish

**Genre names:** Our model uses `Social Issues`, but the current database still contains `World`. We need to coordinate the database tag update before using the classifier automatically.

**Automatic integration:** The Story-generation workflow does not call the classifier yet. For now, we can test it manually.

**Model setup:** Each machine running the classifier needs the downloaded model and the correct local path.

The classifier has already been tested with Supabase, so the remaining work is mainly connecting it to the rest of the application.
