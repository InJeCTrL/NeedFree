import asyncio
import aiohttp
import datetime
import time
import json
import pytz
import bs4
import sys
import random
from dataclasses import dataclass
from threading import Lock


API_URL_TEMPLATE = "https://store.steampowered.com/search/results/?query&start={pos}&count=100&infinite=1"


@dataclass
class Stats:
    """统计信息"""
    total_goods: int = 0
    free_goods: int = 0
    pages_completed: int = 0
    lock: Lock = None
    
    def __post_init__(self):
        self.lock = Lock()
    
    def update_display(self):
        """更新显示"""
        with self.lock:
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            msg = f"[{current_time}] 📊 总商品: {self.total_goods} | 免费商品: {self.free_goods} | 已完成页数: {self.pages_completed}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()


stats = Stats()


def log(message):
    """带时间戳的日志输出"""
    current_time = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"[{current_time}] {message}")


stats = Stats()

async def fetch_Steam_json_response(session, url):
    ''' Fetch json response from Steam API using async
    session:        aiohttp session
    url:            Steam WebAPI url

    return:         json content or None if failed
    '''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,zh-HK;q=0.7,en-US;q=0.6,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=4',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }
    
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                ret_json = await response.json()
                return ret_json
            else:
                return None
                
    except:
        return None

async def get_free_goods(session, start):
    ''' Extract 100%-discount goods list in a list of 100 products
    session:        aiohttp session
    start:          start page index

    return:         (goods_count, free_list)
    '''
    url = API_URL_TEMPLATE.format(pos=start)
    
    # 无限重试，直到成功
    while True:
        response_json = await fetch_Steam_json_response(session, url)
        
        if response_json is None:
            print('Retrying...')
            await asyncio.sleep(1)
            continue
        
        try:
            goods_count = response_json["total_count"]
            
            # 动态更新总商品数，取最大值
            with stats.lock:
                if goods_count > stats.total_goods:
                    stats.total_goods = goods_count
            
            goods_html = response_json["results_html"]
            page_parser = bs4.BeautifulSoup(goods_html, "html.parser")
            full_discounts_div = page_parser.find_all(
                name="div", 
                attrs={"class": "search_discount_block", "data-discount": "100"}
            )
            
            sub_free_list = []
            for div in full_discounts_div:
                try:
                    parent = div.parent.parent.parent.parent
                    title = parent.find(name="span", attrs={"class": "title"}).get_text()
                    href = parent.get("href")
                    sub_free_list.append([title, href])
                except:
                    continue
            
            # 更新统计
            with stats.lock:
                stats.free_goods += len(sub_free_list)
                stats.pages_completed += 1
            
            stats.update_display()
            return (goods_count, sub_free_list)
            
        except:
            print('Retrying...')
            await asyncio.sleep(1)
            continue

async def main():
    log("=" * 60)
    log("🚀 NeedFree 爬虫启动 (顺序模式)")
    log("=" * 60)
    log("⚙️  请求间隔: 1-4秒随机延迟")
    log("-" * 60)
    
    # 创建 aiohttp session
    timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        all_results = []
        current_page = 0
        
        # 顺序爬取页面
        while True:
            start = current_page * 100
            
            # 如果不是第一页，添加随机延迟
            if current_page > 0:
                delay = 1 + random.uniform(0, 3)
                await asyncio.sleep(delay)
            
            # 获取当前页
            goods_count, sub_free_list = await get_free_goods(session, start)
            all_results.append((goods_count, sub_free_list))
            
            # 检查是否已经爬完所有页面
            with stats.lock:
                total_count = stats.total_goods
            
            current_page += 1
            
            # 如果当前页的起始位置已经超过总商品数，说明爬完了
            if start + 100 >= total_count:
                break
        
        print()  # 换行
        log("-" * 60)
        log("✅ 所有页面爬取完成")
        
        # 去重处理
        log("🔄 去重处理中...")
        final_free_list = []
        free_names = set()
        
        for goods_count, sub_free_list in all_results:
            for free_item in sub_free_list:
                game_name = free_item[0]
                if game_name not in free_names:
                    free_names.add(game_name)
                    final_free_list.append(free_item)
        
        log(f"✅ 去重后: {len(final_free_list)} 个免费游戏")
        
        # 保存结果
        log("💾 保存结果...")
        with open("free_goods_detail.json", "w", encoding="utf-8") as fp:
            json.dump({
                "total_count": len(final_free_list),
                "free_list": final_free_list,
                "update_time": datetime.datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
            }, fp, ensure_ascii=False, indent=2)
        
        log("=" * 60)
        log(f"🎉 完成！共找到 {len(final_free_list)} 个免费游戏")
        log("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())