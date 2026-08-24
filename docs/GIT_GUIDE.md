# GitHub 团队协作指南

> 适用对象：没有 Git 团队协作经验的 A/B/C/D  
> 比赛期间只使用本指南中的流程，不自行尝试 rebase、force push、reset hard 或复杂分支操作。

## 一、先理解六个词

- 仓库 repo：项目文件夹的联网版本；
- 分支 branch：个人独立工作区；
- 提交 commit：一次有说明的修改记录；
- 推送 push：把本地提交上传到 GitHub；
- 拉取 pull：把 GitHub 最新内容下载到本地；
- Pull Request：请求把个人分支合并进 main；
- 冲突 conflict：两个人修改了同一位置，Git 无法自动判断保留谁。

## 二、团队分支

~~~text
main                 稳定版本
role-a-core          A
role-b-ingestion     B
role-c-industry      C
role-d-eval-ui       D
~~~

所有人禁止直接在 main 写代码或提交。

## 三、第一次使用

### 1. 检查 Git

在终端运行：

~~~powershell
git --version
~~~

如果无法识别命令，先安装 Git，再继续。不要在编码工具不知情的情况下让它自动安装多个 Git 客户端。

### 2. 配置姓名和邮箱

~~~powershell
git config --global user.name "你的姓名"
git config --global user.email "你的GitHub邮箱"
~~~

检查：

~~~powershell
git config --global user.name
git config --global user.email
~~~

### 3. 克隆仓库

把 REPO_URL 替换为项目仓库地址：

~~~powershell
git clone REPO_URL
cd finresearch
git status
~~~

正常状态应显示当前分支和工作区没有待提交修改。

### 4. 切换自己的分支

A：

~~~powershell
git fetch origin
git switch --track origin/role-a-core
~~~

B：

~~~powershell
git fetch origin
git switch --track origin/role-b-ingestion
~~~

C：

~~~powershell
git fetch origin
git switch --track origin/role-c-industry
~~~

D：

~~~powershell
git fetch origin
git switch --track origin/role-d-eval-ui
~~~

如果提示分支已经存在：

~~~powershell
git switch 你的分支名
~~~

检查：

~~~powershell
git branch --show-current
git status
~~~

开始工作前，必须确认自己不在 main。

## 四、每天开始工作

先确认没有未保存修改：

~~~powershell
git status
~~~

如果有修改，先完成测试并提交，不要直接拉取。

确认干净后：

~~~powershell
git fetch origin
git switch 你的分支名
git merge origin/main
~~~

如果出现 conflict、CONFLICT 或 Automatic merge failed，立即停止，不要删除文件，也不要执行 reset。把完整错误发给 A。

## 五、完成一个任务后

### 1. 查看修改

~~~powershell
git status
git diff
~~~

确认只修改了任务范围内的文件。

### 2. 运行测试

B 示例：

~~~powershell
pytest tests/ingestion -q
~~~

C 示例：

~~~powershell
pytest tests/industry -q
~~~

D 示例：

~~~powershell
pytest tests/evaluation -q
~~~

A 示例：

~~~powershell
pytest tests/core tests/integration -q
~~~

### 3. 添加指定文件

不要直接使用 git add .。只添加自己确认过的文件。

示例：

~~~powershell
git add app/ingestion/manifest.py
git add tests/ingestion/test_manifest.py
~~~

再次检查：

~~~powershell
git status
~~~

### 4. 提交

~~~powershell
git commit -m "feat(ingestion): add manifest validation"
~~~

推荐类型：

~~~text
feat       新功能
fix        修复
test       测试
docs       文档
refactor   不改变功能的整理
chore      配置或杂项
~~~

提交说明示例：

~~~text
feat(industry): add banking risk rules
test(evaluation): add cutoff red-team case
fix(core): reject evidence after cutoff date
docs(role-b): update evidence handoff steps
~~~

### 5. 推送

第一次：

~~~powershell
git push -u origin 你的分支名
~~~

之后：

~~~powershell
git push
~~~

## 六、创建 Pull Request

1. 打开 GitHub 仓库；
2. 点击 Pull requests；
3. 点击 New pull request；
4. base 选择 main；
5. compare 选择自己的角色分支；
6. 填写标题和说明；
7. 创建 Pull Request；
8. 把链接发到群里。

PR 说明模板：

~~~text
任务：
修改文件：
实现结果：
测试命令：
测试结果：
未解决问题：
需要重点审查：
~~~

B/C/D 的 PR 由 A 审查和合并。A 的 PR 由 D 按运行说明验证，确认后由 A 合并。

比赛期间使用普通 Merge pull request，不使用 Squash and merge，避免长期角色分支历史混乱。

## 七、PR 合并后

等待 A 通知合并完成，再运行：

~~~powershell
git fetch origin
git switch 你的分支名
git merge origin/main
git push
~~~

如果出现冲突，停止并联系 A。

## 八、出现错误时怎么办

### 提示 not a git repository

说明当前终端不在仓库目录。

~~~powershell
Get-Location
Get-ChildItem
~~~

切换到项目目录后再运行 Git。

### 提示 working tree has changes

说明有未提交修改。

~~~powershell
git status
git diff
~~~

不要强行 pull。先确认修改、运行测试并提交。

### 提示 rejected 或 non-fast-forward

不要 force push。

~~~powershell
git fetch origin
git merge origin/你的分支名
~~~

若发生冲突，联系 A。

### 提示 merge conflict

立即停止，把以下内容发给 A：

~~~powershell
git status
~~~

不要自行删除冲突标记，不要使用 reset hard。

## 九、禁止命令

没有 A 明确指导时，禁止：

~~~text
git reset --hard
git push --force
git push -f
git rebase
git clean -fd
git checkout .
git restore .
git branch -D
~~~

这些命令可能覆盖或删除尚未保存的工作。

## 十、编码工具的 Git 指令

可以让编码工具帮助检查状态和生成提交说明，但不要授权它自动执行合并或强制操作。

推荐指令：

~~~text
请先运行 git status 和 git branch --show-current。

只分析当前状态，不要执行 reset、rebase、force push、clean、
checkout、restore、merge 或删除操作。

告诉我：
1. 当前分支；
2. 修改了哪些文件；
3. 是否超出我的任务范围；
4. 应该运行哪些测试；
5. 建议的 commit message。
~~~

提交前：

~~~text
请检查当前 diff，确认没有修改其他角色目录。
不要提交，不要推送。只输出需要 git add 的明确文件列表、
测试命令和建议的提交说明。
~~~

## 十一、每日 Git 检查清单

开始工作：

- [ ] 当前不是 main；
- [ ] git status 已检查；
- [ ] 已同步 origin/main；
- [ ] 当前任务已写入 task_board。

提交前：

- [ ] 只修改自己的目录；
- [ ] 看过 git diff；
- [ ] 测试通过；
- [ ] 使用明确文件执行 git add；
- [ ] commit 只对应一个任务。

PR 前：

- [ ] 已 push；
- [ ] PR base 是 main；
- [ ] PR compare 是自己的角色分支；
- [ ] 写明测试命令和结果；
- [ ] 通知审查人。


