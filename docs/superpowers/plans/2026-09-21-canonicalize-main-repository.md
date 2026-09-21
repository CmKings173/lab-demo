# Canonicalize Main Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Giữ nguyên và publish commit `14e7e8943d830b2a766f1d837837ea5d22729d73`, đưa source cùng documentation commit mới từ linked worktree vào main working tree `D:\project\lab demo`, publish an toàn lên `https://github.com/CmKings173/lab-demo.git`, và không xóa worktree cho tới khi có bằng chứng đầy đủ.

**Architecture:** Sau khi người dùng duyệt, commit hai file documentation mới trên branch `codex/foundation-hardening-v3-vi-dataset` với parent là `14e7e89`, rồi dùng fast-forward-only vào branch hiện đang checkout tại main working tree `codex/phase-0-1-foundation`. Không copy source, không tạo repository thứ hai, không reset và không force push. README tiếng Việt độc lập nằm trong chính source tree để không ghi đè README hiện hữu.

**Tech Stack:** Git linked worktree, Python 3.11+, Pydantic, pytest, Ruff, JSONL dataset artifacts, GitHub HTTPS remote.

**Spec:** Yêu cầu người dùng ngày 2026-09-21 về canonical local source, bảo toàn commit `14e7e89`, publish GitHub an toàn và README tiếng Việt đầy đủ.

## Global Constraints

- Không dùng `git reset --hard`, `git checkout --`, `git worktree remove`, `Remove-Item` trên source, hoặc `git push --force`.
- Không đổi business logic, dataset content, contracts, workflow, tests, pricing, RAG, proposal hay validation.
- Không tạo repo mới và không copy source sang thư mục khác.
- Chỉ publish sau khi main working tree sạch, commit đích đã tồn tại và remote kiểm chứng được.
- Nếu GitHub yêu cầu authentication/user interaction, dừng và báo rõ; không lưu credential vào repo.
- Không xóa linked worktree trước bước hậu kiểm remote và commit reachability.

---

### Task 0: Commit documentation mới trước khi đồng bộ source

**Files:**
- Add: `README.vi.md`
- Add: `docs/superpowers/plans/2026-09-21-canonicalize-main-repository.md`

**Interfaces:**
- Consumes: clean code commit `14e7e8943d830b2a766f1d837837ea5d22729d73` và hai file documentation đã được người dùng xem xét.
- Produces: một documentation commit mới trên cùng branch, không sửa business logic.

- [ ] **Step 1: Review diff chỉ gồm documentation**

```powershell
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" status --short
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" diff --check
```

Expected: chỉ có `README.vi.md` và file plan chưa tracked; không có file trong
`lab1_finetune/`, `lab2_rag_agent/`, `lab3_workflow/`, `shared/` hoặc `adapters/`.

- [ ] **Step 2: Tạo documentation commit**

```powershell
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" add README.vi.md docs/superpowers/plans/2026-09-21-canonicalize-main-repository.md
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" diff --cached --check
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" commit -m "docs: add Vietnamese project guide"
```

- [ ] **Step 3: Xác nhận commit gốc không bị thay thế**

```powershell
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" log -2 --oneline --decorate
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" status
```

Expected: commit mới có parent là `14e7e89`, và working tree clean.

---

### Task 1: Freeze và xác nhận preconditions

**Files:**
- Read-only: `D:\project\lab demo`
- Read-only: `D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset`

**Interfaces:**
- Consumes: main branch `codex/phase-0-1-foundation`, feature branch `codex/foundation-hardening-v3-vi-dataset`.
- Produces: bằng chứng main sạch, worktree sạch, commit đích đúng và main là ancestor của commit đích.

- [ ] **Step 1: Kiểm tra trạng thái main và linked worktree**

```powershell
git -C "D:\project\lab demo" status
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" status
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" rev-parse HEAD
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" worktree list --porcelain
```

Expected: cả hai working tree clean; commit worktree là
`14e7e8943d830b2a766f1d837837ea5d22729d73`.

- [ ] **Step 2: Kiểm tra ancestry trước khi merge**

```powershell
$mainHead = git -C "D:\project\lab demo" rev-parse HEAD
$targetHead = git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" rev-parse HEAD
git -C "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset" merge-base --is-ancestor $mainHead $targetHead
```

Expected: exit code `0`. Nếu khác `0`, dừng; không tự merge hai phía.

### Task 2: Cấu hình và kiểm tra GitHub remote không phá history

**Files:**
- Modify Git metadata only: `.git/config` của repository dùng chung.

**Interfaces:**
- Consumes: remote URL chính xác `https://github.com/CmKings173/lab-demo.git`.
- Produces: `origin` trỏ đúng URL và branch feature được push không force.

- [ ] **Step 1: Kiểm tra remote hiện tại**

```powershell
git -C "D:\project\lab demo" remote -v
git ls-remote --heads "https://github.com/CmKings173/lab-demo.git"
```

Nếu chưa có `origin`, chạy đúng lệnh sau:

```powershell
git -C "D:\project\lab demo" remote add origin "https://github.com/CmKings173/lab-demo.git"
```

Nếu `origin` đã tồn tại nhưng khác URL, dừng để người dùng xác nhận; không tự
`remote set-url`.

- [ ] **Step 2: Kiểm tra push mà chưa tạo remote ref**

```powershell
git -C "D:\project\lab demo" push --dry-run origin codex/foundation-hardening-v3-vi-dataset
```

Expected: dry-run không báo non-fast-forward hoặc authentication failure.

- [ ] **Step 3: Push branch chứa commit đích**

```powershell
git -C "D:\project\lab demo" push -u origin codex/foundation-hardening-v3-vi-dataset
```

Nếu lệnh cần đăng nhập tương tác, dừng tại đây; không thay credential hoặc force
push.

### Task 3: Fast-forward main working tree vào source canonical

**Files:**
- Modify branch/worktree state only: `D:\project\lab demo`.

**Interfaces:**
- Consumes: remote branch đã chứa commit `14e7e89`; main working tree clean.
- Produces: main working tree checkout trực tiếp toàn bộ `lab1_finetune/`,
  `lab2_rag_agent/`, `lab3_workflow/`, `shared/`, `adapters/`, `docs/` và dataset.

- [ ] **Step 1: Re-check main is still clean**

```powershell
git -C "D:\project\lab demo" status --porcelain=v1
```

Expected: không có output. Nếu có output, dừng và không stash/reset tự động.

- [ ] **Step 2: Fast-forward-only từ feature branch**

```powershell
git -C "D:\project\lab demo" merge --ff-only codex/foundation-hardening-v3-vi-dataset
```

Lệnh này bảo toàn toàn bộ commit history và không tạo merge commit. Nếu Git báo
không fast-forward, dừng để review divergence.

- [ ] **Step 3: Xác nhận main đã ở commit đích**

```powershell
git -C "D:\project\lab demo" rev-parse HEAD
git -C "D:\project\lab demo" status
git -C "D:\project\lab demo" ls-tree --name-only HEAD
```

Expected: HEAD là `14e7e89`, working tree clean và tree có các package canonical.

### Task 4: Verify source tree và dataset sau fast-forward

**Files:**
- Read-only: `D:\project\lab demo\lab1_finetune\data\`

**Interfaces:**
- Consumes: main tree sau fast-forward.
- Produces: bằng chứng path tuyệt đối và dataset artifacts vẫn nằm trong một repo.

- [ ] **Step 1: Kiểm tra paths bắt buộc**

```powershell
$root = "D:\project\lab demo"
@(
  "lab1_finetune",
  "lab2_rag_agent",
  "lab3_workflow",
  "shared",
  "adapters",
  "docs",
  "data",
  "README.md",
  "pyproject.toml",
  "lab1_finetune\data\gold_specs.json",
  "lab1_finetune\data\seed\gold_seed_vi.jsonl",
  "lab1_finetune\data\splits\train.jsonl",
  "lab1_finetune\data\splits\validation.jsonl",
  "lab1_finetune\data\splits\test.jsonl",
  "lab1_finetune\data\manifests\gold_seed_vi_manifest.json"
) | ForEach-Object { Test-Path (Join-Path $root $_) }
```

Expected: tất cả trả `True`.

- [ ] **Step 2: Chạy verification gates từ main root**

```powershell
Set-Location "D:\project\lab demo"
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
python -m compileall -q .
python -m lab1_finetune.data.build_artifacts
python -m pytest
git diff --check
git status
```

Expected: test/lint/compile/build pass và main working tree vẫn clean.

### Task 5: Publish canonical main branch state

**Files:**
- Modify remote refs only after Tasks 1–4 pass.

**Interfaces:**
- Consumes: main branch hiện tại `codex/phase-0-1-foundation` đã fast-forward tới
  commit `14e7e89`.
- Produces: remote branch chứa đúng commit; không đổi tên branch hoặc force push.

- [ ] **Step 1: Dry-run push main branch**

```powershell
git -C "D:\project\lab demo" push --dry-run -u origin codex/phase-0-1-foundation
```

- [ ] **Step 2: Push main working tree branch**

```powershell
git -C "D:\project\lab demo" push -u origin codex/phase-0-1-foundation
```

- [ ] **Step 3: Verify remote reachability**

```powershell
git -C "D:\project\lab demo" ls-remote origin refs/heads/codex/foundation-hardening-v3-vi-dataset refs/heads/codex/phase-0-1-foundation
git -C "D:\project\lab demo" branch -vv
git -C "D:\project\lab demo" status
```

Expected: cả hai remote refs đều trỏ tới commit chứa `14e7e89`, branch local có
upstream và main working tree clean.

### Task 6: Defer linked-worktree cleanup

**Files:**
- Không thay đổi ở task hiện tại.

**Interfaces:**
- Consumes: bằng chứng remote reachability từ Task 5.
- Produces: không xóa checkout nào cho tới khi người dùng yêu cầu riêng.

- [ ] **Step 1: Không chạy cleanup command trong lần này**

Không chạy:

```powershell
git worktree remove "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset"
Remove-Item -Recurse -Force "D:\project\lab demo\.worktrees\foundation-hardening-v3-vi-dataset"
```

Nếu sau này cần dọn worktree, phải có một task riêng sau khi đã xác nhận commit
remote, main tree sạch và không còn thay đổi chưa publish.

## Verification checklist

- [ ] Main working tree sạch trước merge.
- [ ] Commit `14e7e8943d830b2a766f1d837837ea5d22729d73` tồn tại trước merge.
- [ ] Main là ancestor của commit đích.
- [ ] Feature branch được push non-force.
- [ ] Main được cập nhật bằng `merge --ff-only`.
- [ ] Dataset vẫn nằm ở `lab1_finetune/data/`.
- [ ] Full verification chạy từ `D:\project\lab demo`.
- [ ] Main branch được push và remote reachability được xác nhận.
- [ ] Không xóa linked worktree trong task này.
