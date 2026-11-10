# 喵喵 GitHub 常用指令

仓库：`/home/kali/miaomiao`  
远程：`https://github.com/qwnm2010/miaomiao-uninstaller.git`

## 1. 上传更新

```bash
cd /home/kali/miaomiao
git add -A
git commit -m "update"
git push
```

**解释**

- `git add -A`：收集所有修改
- `git commit`：保存成本地一次提交
- `git push`：把提交上传到 GitHub

## 2. 重新打包

```bash
cd /home/kali/miaomiao
./build-deb.sh
(cd dist && sha256sum miaomiao_1.6.0_amd64.deb > SHA256SUMS && sha256sum -c SHA256SUMS)
git add -A
git commit -m "rebuild package"
git push
```

**解释**

- `build-deb.sh`：重新生成 `dist/miaomiao_1.6.0_amd64.deb`
- `sha256sum`：更新并检查校验文件
- 版本号变化时，替换命令里的 `1.6.0`

## 3. 登录

```text
Username: qwnm2010
Password: 粘贴 Personal Access Token
```

**解释**

密码输入时不显示字符，粘贴后直接回车。不要填 GitHub 登录密码。

## 4. 检查

```bash
cd /home/kali/miaomiao
git status -sb
```

**解释**

- `## main...origin/main`：已同步
- `ahead 1`：本地有 1 个提交还没 push

## 5. 出问题

**push 后没有输出**

在等账号密码，粘贴 token 回车。

**push 被拒绝**

```bash
git pull --rebase origin main
git push
```

**GitHub 还是旧内容**

先看 `git status -sb`；有 `ahead` 就再 `git push`。

**不要用网页 Upload files 传项目，用 `git push`。**
