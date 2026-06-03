# 安装指南

打开 cmd（按 Win+R，输入 cmd，回车），逐行复制粘贴下面的命令。

---

## 第一步：装 Python

```
winget install Python.Python.3.12
```

装完后**关闭 cmd 重新打开**。

---

## 第二步：装 Node.js

```
winget install OpenJS.NodeJS.LTS
```

---

## 第三步：进入项目目录

```
cd C:\你的路径\novel-pipeline-write-engine
```

（把路径换成你解压的实际位置）

---

## 第四步：安装依赖

```
pip install -r requirements.txt -r requirements-api.txt
```

```
cd frontend
npm install
cd ..
```

---

## 第五步：启动

```
python start.py
```

浏览器会自动打开。

---

## 以后每次使用

打开 cmd，输入：

```
cd C:\你的路径\novel-pipeline-write-engine
python start.py
```
