### Build Script
    python -m PyInstaller --hidden-import aiomysql -n "novelAI" .\main.py
---
#### 20260301
> 聚合AI功能到AINexus单例模式  
> 调整logger  
> 
#### 20260305
> 所有功能接口完成

#### 20260311
> 新增提示词工具接口；  
> 可以根据提示词渲染对应的文本；  
> 调整书籍创建接口，去除无用参数，增加type字段，统一节点参数；  
> 修复节点接口不返回data json数据的bug；  
> 优化部分DAO整合db代码。

#### 20260312
> generate新增name拼接根据 type>1 查询出name:content 拼接

#### 20260316
> node type 节点类型bug修改