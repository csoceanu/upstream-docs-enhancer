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
   Once set up, any time you open a Pull Request (PR) in your code repository, the enhancer will automatically:

   - Analyze the changes
   - Generate documentation suggestions
   - Open a new PR in your upstream documentation repository with the proposed updates
