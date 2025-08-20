## How to Use the Upstream Documentation Enhancer

To use the **Upstream Documentation Enhancer**, follow these steps:

1. **Add the Enhancer to Your Repository**  
   Copy the files from the `upstream-docs-enhancer` repository into your code repository.

2. **Set Up GitHub Actions Secrets**  
   In your code repository, configure the following secrets:

   - `DOCS_REPO_URL`: URL of your upstream documentation repository  
   - `GEMINI_API_KEY`: Your Gemini API key  
   - `GH_PAT`: Your GitHub Personal Access Token

3. **Trigger the Pipeline**  
   Once set up, the enhancer will automatically run when someone comments `[update-docs]` on a Pull Request (PR). The enhancer will:

   - Analyze the changes
   - Generate documentation suggestions
   - Open a new PR in your upstream documentation repository with the proposed updates
