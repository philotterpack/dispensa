param(
	[Parameter(Mandatory=$true)][string]$RepoName,     # repo name or "user/repo"
	[switch]$Private                                  # include -Private for a private repo
)

# ...existing code...
try {
	# project root = parent of this scripts folder
	$projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..') | Select-Object -ExpandProperty Path
	Write-Host "Project root: $projectRoot"

	# check gh availability
	if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
		Write-Error "GitHub CLI 'gh' not found. Install it: https://cli.github.com/ and run 'gh auth login' before using this script."
		exit 1
	}

	Set-Location $projectRoot

	# init git if needed
	if (-not (git rev-parse --is-inside-work-tree 2>$null)) {
		git init
		Write-Host "Initialized empty git repository."
	}

	# ensure branch main exists
	try {
		git rev-parse --verify main >/dev/null 2>&1
	} catch {
		git checkout -b main
	}

	# add & commit
	git add -A
	# commit only if there are staged changes
	$hasChanges = (git status --porcelain)
	if ($hasChanges) {
		git commit -m "Initial commit"
	} else {
		Write-Host "No changes to commit."
	}

	# create GitHub repo and push using gh
	$vis = if ($Private) { 'private' } else { 'public' }
	Write-Host "Creating GitHub repository '$RepoName' ($vis)..."
	gh repo create $RepoName --$vis --source=. --remote=origin --push -y

	Write-Host "Push completed. Remote origin configured."
}
catch {
	Write-Error "Error: $_"
	exit 1
}