# Give the dashboard a public link

A GitHub Codespaces `*.app.github.dev` address is a development preview. Don't put it on a résumé: access, uptime and the Codespace's lifetime are not suitable for a public portfolio. Use [Streamlit Community Cloud](https://share.streamlit.io/) to obtain a stable, public `*.streamlit.app` address.

Our raw Hillstrom CSV and full local SQLite database are intentionally not committed. A new Streamlit deployment otherwise starts without any saved results. That's why the project includes a **public results export** containing only aggregate charts and model summaries—not individual customer records or individual model scores.

### One-time setup in your existing GitHub Codespace

1. First merge the latest reviewed pull request on GitHub. In your Codespaces terminal, run `git pull origin main`. Make sure any other local edits are committed or saved before pulling.
2. Rebuild your real results and run the independent audit. If dataset download fails but `data/raw/hillstrom.csv` already exists, it will be reused. Do **not** use `--synthetic` for publication.

```bash
python -m src.pipeline
python -m src.audit --require-real
```

3. When the audit passes, export only the aggregate data. **Inspect which file Git will commit**:

```bash
python -m src.export_public
git status --short
git add data/dashboard.db
git commit -m "Add verified historical dashboard aggregates"
git push origin main
```

The public database includes aggregate campaign statistics, segment statistics, and model evaluation curves. It excludes the raw CSV, `customers` table and row-level `uplift_holdout` scores. Do not commit other data files.

### Deploy the public website

1. Open [Streamlit Community Cloud](https://share.streamlit.io/), sign in with GitHub, and choose **Create app → I have an app**.
2. Select repository `Thizisfranklin/Retail-Promotion-Targeting-Uplift-Modeling`, branch `main`, main file `app.py`.
3. Under **Advanced settings**, select **Python 3.11** to match the project's verification environment. Click **Deploy**.
4. Once it loads, confirm the dashboard displays real 64,000-customer results and the three charts, with **no synthetic-data warning**. In the app's sharing settings make it public, then copy the `*.streamlit.app` URL.
5. Add the permanent link to the **Explore the interactive dashboard** section in `README.md` and your repository's **About → Website** field. You can also feature it on your résumé or LinkedIn.

Afterward, whenever you edit code on `main`, Community Cloud can redeploy it. If you change the analyses, regenerate and recommit the verified aggregate database before advertising the new numbers. A public visitor explores historical, precomputed results; opening the page does not send emails or retrain models.

Troubleshooting: A fresh app reporting **No analysis available** usually means `data/dashboard.db` was not committed to `main`. An app displaying synthetic data means you attempted to export the wrong dataset—the export command is designed to reject this. If Streamlit Cloud cannot install dependencies, check its build logs and `requirements.txt`.
