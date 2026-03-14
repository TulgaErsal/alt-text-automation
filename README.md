# Alt Text Automation for PowerPoint

Batch-generates AI alt text for every picture in a `.pptx` file using the
[UMich AI Helper Alt Text Generator](https://aihelper.engin.umich.edu/alt-text-generator).
The script automates a browser session: you sign in once with your institutional
Google account, then it submits each image to the tool, waits for the AI response,
and writes the result back into the PowerPoint file.

---

## Contents

| File | Purpose |
|---|---|
| `generate_alt_text.py` | Core script (also usable as a CLI) |
| `gui.py` | Desktop GUI front-end (CustomTkinter) |
| `geckodriver.exe` | Firefox WebDriver (pre-bundled for Windows) |

---

## Requirements

### Python

Python 3.10 or later is required (the script uses the `X | Y` union type syntax).

Download from [python.org](https://www.python.org/downloads/) and make sure
`python` is on your system `PATH`.

### Python packages

Install all required packages with one command:

```
pip install selenium python-pptx Pillow cairosvg customtkinter
```

| Package | Version tested | Purpose |
|---|---|---|
| `selenium` | 4.6 or later | Browser automation |
| `python-pptx` | any recent | Read/write `.pptx` files |
| `Pillow` | any recent | Convert BMP/TIFF/EMF/WMF images to PNG |
| `cairosvg` | any recent | Convert SVG images to PNG |
| `customtkinter` | any recent | Desktop GUI (`gui.py` only) |

> **`cairosvg`** is optional — the script still works without it, but SVG
> shapes will fail with a descriptive error message rather than being skipped
> silently.

> EMF and WMF conversion uses Pillow, which does not handle complex metafiles well.

> **Selenium 4.6+** bundles Selenium Manager, which automatically downloads
> the correct ChromeDriver or Edge WebDriver when you use Chrome or Edge.
> No manual driver installation is needed for those browsers.

### Browser

The script supports **Firefox**, **Chrome**, and **Edge** (auto-detected in
that order). At least one must be installed.

- **Firefox** — [mozilla.org/firefox](https://www.mozilla.org/firefox/)
  The repository includes `geckodriver.exe` for Windows, so no additional
  setup is needed.
- **Chrome** — [google.com/chrome](https://www.google.com/chrome/)
  ChromeDriver is downloaded automatically by Selenium Manager.
- **Edge** — pre-installed on Windows 10/11.
  Edge WebDriver is downloaded automatically by Selenium Manager.

### Network access

You must be able to reach `https://aihelper.engin.umich.edu` and have a valid
University of Michigan (or affiliated institution) Google account.

---

## Installation

1. **Clone or download** this folder to your machine.

2. **Install Python packages:**

   ```
   pip install selenium python-pptx Pillow cairosvg customtkinter
   ```

3. **Verify geckodriver** (Firefox only):
   `geckodriver.exe` is already present in the project folder and will be
   used automatically. If you prefer a different version, replace it with a
   build from [github.com/mozilla/geckodriver/releases](https://github.com/mozilla/geckodriver/releases)
   matching your Firefox version.

---

## Usage

### GUI (recommended)

```
python gui.py
```

A desktop window opens with all options available as form controls.

1. **Select input PPTX** — use the Browse button or type a path. The output
   path is filled in automatically as `<name>_alt_text.pptx`.
2. **Adjust options** — alt text version, browser, purpose, tone, include
   checkboxes. The Geckodriver path field under Advanced (Firefox only) can be
   left blank if `geckodriver.exe` is in the same folder as the script — it is
   detected automatically.
3. **Click Run.** The browser opens; sign in with your institutional Google
   account. Progress streams into the Log area in real time.
4. **Click Stop** (red button) at any time to abort after the current image
   finishes. Slides processed so far are saved to the output file.
5. **Clear** the Log area with the Clear button above it.

### Command line

```
python generate_alt_text.py <input.pptx> [options]
```

### Minimal example

```
python generate_alt_text.py slides.pptx
```

This processes `slides.pptx`, generates the **long** version of alt text for
every picture (the default), and saves the result as `slides_alt_text.pptx`
in the same folder.

### All options

```
python generate_alt_text.py slides.pptx
    [--url URL]
    [--output OUTPUT.pptx]
    [--version {short,medium,long}]
    [--browser {auto,firefox,chrome,edge}]
    [--geckodriver PATH]
    [--purpose {general,educational,instructional,marketing,icon}]
    [--include {data-values,captions} ...]
    [--tone {formal,academic,professional,neutral,conversational,casual,colloquial}]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--url` | `-u` | `https://aihelper.engin.umich.edu/alt-text-generator` | Full URL of the Alt Text Generator page |
| `--output` | `-o` | `<stem>_alt_text.pptx` | Output file path |
| `--version` | `-v` | `long` | Which alt text length to embed: `short` (≈ 1 sentence), `medium` (≈ 2–3 sentences), or `long` (full description) |
| `--browser` | `-b` | `auto` | Browser to use. `auto` tries Firefox → Chrome → Edge |
| `--geckodriver` | `-g` | `geckodriver.exe` in script folder | Path to `geckodriver` executable (Firefox only). Can be omitted if `geckodriver.exe` is in the same folder as the script — it is detected automatically. |
| `--purpose` | `-p` | *(none)* | Purpose/Use Case radio button — see table below |
| `--include` | `-i` | *(none)* | Checkboxes to tick — can be repeated |
| `--tone` | `-t` | *(none)* | Tone of the generated alt text — see table below |

---

## Form options

### Purpose / Use Case (`--purpose`)

Selects the radio button on the form that describes the image's intended use.

| Value | Label on the form |
|---|---|
| `general` | General Description (for decorative or illustrative images) |
| `educational` | Detailed Educational Description (for charts, diagrams, maps etc) |
| `instructional` | Instructional Use (used in tutorials or learning modules) |
| `marketing` | Marketing or Promotional Use |
| `icon` | Interface Icon or Button |

### Include (`--include`)

Ticks one or both optional checkboxes. The flag may be repeated or given
multiple values separated by spaces.

| Value | Label on the form |
|---|---|
| `data-values` | Include Data Values |
| `captions` | Include Captions/Labels |

Example — tick both:

```
python generate_alt_text.py slides.pptx --include data-values captions
```

### Tone (`--tone`)

Selects the tone from the dropdown menu.

| Value | Tone |
|---|---|
| `formal` | Formal |
| `academic` | Academic |
| `professional` | Professional |
| `neutral` | Neutral |
| `conversational` | Conversational |
| `casual` | Casual |
| `colloquial` | Colloquial |

---

## Step-by-step walkthrough

1. **Run the script.** A browser window opens and navigates to the Alt Text
   Generator page.

2. **Sign in.** The script prints a message:

   ```
   ============================================================
   Please sign in with your institutional Google account.
   Waiting up to 5 minutes ...
   ============================================================
   ```

   Complete the Google authentication in the browser. The script waits up to
   5 minutes. Once your profile link appears in the page header, it
   automatically continues.

3. **Batch processing.** The script processes each picture shape in the
   presentation in order, printing progress:

   ```
   [1/3] Slide 1 — 'Picture 2' (image/png)
     OK — A bar chart showing annual revenue from 2018 to 2023 ...

   [2/3] Slide 2 — 'Picture 5' (image/jpeg)
     OK — A photograph of the engineering building exterior ...

   [3/3] Slide 3 — 'Graphic 4' (image/x-emf)
     OK — A diagram showing the system architecture with three connected components ...
   ```

4. **Output file.** When all images are processed the modified presentation
   is saved and a summary is printed:

   ```
   ────────────────────────────────────────────────────────────
   Total images : 3
     Processed  : 3
     Skipped    : 0
     Errors     : 0
   Output saved : slides_alt_text.pptx
   ```

5. **Review in PowerPoint.** Open the output file. Right-click any picture →
   **View Alt Text** to see the generated description in the Alt Text pane.

---

## Examples

Generate short alt text using the academic tone:

```
python generate_alt_text.py slides.pptx --version short --tone academic
```

Generate long alt text for educational charts, including data values and captions:

```
python generate_alt_text.py slides.pptx \
    --purpose educational \
    --include data-values captions \
    --version long
```

Save output to a custom path and force Firefox:

```
python generate_alt_text.py slides.pptx \
    --output "C:\Documents\slides_accessible.pptx" \
    --browser firefox
```

Use a specific geckodriver binary:

```
python generate_alt_text.py slides.pptx \
    --geckodriver "C:\tools\geckodriver.exe"
```

---

## Supported image formats

| Format | Handling |
|---|---|
| JPEG, PNG, GIF, WebP | Uploaded directly |
| BMP, TIFF, EMF, WMF | Converted to PNG automatically (requires Pillow) |
| SVG | Converted to PNG automatically (requires cairosvg) |

> **Tip for vector graphics:** If you have a choice of format when inserting
> vector images into PowerPoint, prefer **SVG** over EMF or WMF. SVG conversion
> via `cairosvg` is reliable and produces clean raster output. EMF/WMF
> conversion through Pillow is best-effort and may fail or produce poor results
> for complex metafiles. In PowerPoint, you can insert an SVG via
> **Insert → Pictures → This Device**, selecting an `.svg` file directly.

---

## Troubleshooting

**Browser window does not open / `SessionNotCreatedException`**
The script auto-detects Firefox, Chrome, and Edge. Make sure at least one is
installed. If Firefox is installed but not detected, specify its path with
`--browser firefox` and verify that `geckodriver.exe` matches your Firefox version.

**Authentication times out**
The script waits up to 5 minutes for sign-in. If your institution requires
additional steps (MFA, VPN, etc.) complete them within that window. You can
increase `AUTH_TIMEOUT` at the top of the script if needed.

**"Could not find tone '...' in the dropdown"**
The error message lists the actual text of all items found in the dropdown.
Check whether the displayed text has changed since this script was written and
update `TONE_OPTIONS` in the script accordingly.

**Generation times out after 120 s**
The AI occasionally takes longer to respond. Increase `GENERATION_TIMEOUT` near
the top of the script (value is in seconds).

**Alt text written but looks wrong / truncated**
Alt text is truncated at 2000 characters (the PPTX `descr` attribute limit).
Use `--version short` or `--version medium` for shorter output.

---

## How it works

1. The script opens a browser and navigates to the tool URL.
2. You authenticate with your institutional Google account once.
3. For each picture shape in the presentation the script:
   - Extracts the image bytes from the `.pptx` package.
   - Converts unsupported formats (BMP, TIFF) to PNG using Pillow.
   - Writes the image to a temporary file.
   - Navigates to a fresh copy of the form.
   - Uploads the image and sets any requested form options (purpose, includes, tone).
   - Clicks **Generate Content** and waits for the AI response to finish streaming.
   - Extracts the short, medium, or long version from the response.
   - Writes the text into the `descr` attribute of the shape's `<p:cNvPr>` XML
     element, which is the field PowerPoint exposes as the alt text description.
4. Saves the modified presentation to the output path.
