# Git workflow demonstration (Phase 1)

The assignment asks for branches, merges, a resolved merge conflict and a commit history.
Run these commands once in PowerShell, inside your project folder, and take screenshots.

## 1. Create and merge a feature branch

```powershell
git checkout -b feature/add-readme-note
# edit README.md: add one sentence at the bottom, save
git add README.md
git commit -m "Add a note to the README"
git checkout main
git merge feature/add-readme-note
git push origin main
```

## 2. Create a merge conflict on purpose and resolve it

```powershell
git checkout -b feature/change-title
# edit the FIRST line of README.md to:  # DevOps Capstone - Version A
git commit -am "Change README title (A)"

git checkout main
# edit the FIRST line of README.md to:  # DevOps Capstone - Version B
git commit -am "Change README title (B)"

git merge feature/change-title
```

Git stops and says `CONFLICT (content)`. Open `README.md`. The first lines look like this:

```
<<<<<<< HEAD
# DevOps Capstone - Version B
=======
# DevOps Capstone - Version A
>>>>>>> feature/change-title
```

Delete the three marker lines and keep the title you want, for example `# DevOps Capstone: End-to-End DevOps Pipeline`. Then:

```powershell
git add README.md
git commit -m "Resolve merge conflict in README title"
git push origin main
```

## 3. Evidence to capture

- `git log --oneline --graph --all` (shows the branches and the merge)
- The conflict markers in the editor
- GitHub: the **Commits** page and the **Branches** page
