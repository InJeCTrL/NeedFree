from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from flask import Flask, jsonify, send_file, request
import threading
import requests
import argparse
import bs4
import json
import math
import time

argParser = argparse.ArgumentParser()
argParser.description = 'For learning use only, DO NOT use it for illegal purposes. -- InJeCTrL'
argParser.add_argument("-k", "--RefreshKey", help = "The key to refresh the crawler.", required=True)
args = argParser.parse_args()


API_URL_template = "https://store.steampowered.com/search/results/?query&start={pos}&count=100&infinite=1"
Free_List = [0, [], "0-0-0 0:0:0"]
Free_List_Updating = [0, [], "0-0-0 0:0:0"]
Totalthread_ThisTurn = 0
m_TotalThread = threading.Lock()
m_Updating = threading.Lock()

def fetchURLresponse(URL):
    '''
    Return raw text from the website
    '''
    while True:
        try:
            response = requests.get(URL, timeout = 5)
            retdata = response.text
            response.close()
            return retdata
        except:
            continue

def getFreeGoodsList(start):
    '''
    Extract 100%-discount goods list in a list of 100 products
    start:      start position
    return:     [goods_count, 100%-discount goods list]
    '''
    retry_time = 3
    while retry_time >= 0:
        responseTxt = fetchURLresponse(API_URL_template.format(pos = start))
        try:
            responseData = json.loads(responseTxt)
            goods_count = responseData["total_count"]
            goods_html = responseData["results_html"]
            page_parser = bs4.BeautifulSoup(goods_html, "html.parser")
            discounts_div = page_parser.find_all(name = "div", attrs = {"class":"search_discount"})
            free_list = []
            for div in discounts_div:
                if div.find("span") and div.span.get_text() == "-100%":
                    node = div.parent.parent.parent
                    free_list.append([node.find(name = "span", attrs = {"class":"title"}).get_text(), node.get("href")])
            return [goods_count, free_list]
        except:
            print("getFreeGoodsList: error on start = %d, remain retry %d time(s)" % (start, retry_time))
            retry_time -= 1
    print("getFreeGoodsList: error on start = %d, throw" % (start))
    return None

def go_each(startlist):
    '''
    Run task for each thread
    startlist:      list of start position
    '''
    global Free_List_Updating
    global Free_List
    global Totalthread_ThisTurn
    for startpos in startlist:
        goods_list = getFreeGoodsList(startpos)
        if goods_list:
            with m_Updating:
                if goods_list[0] > Free_List_Updating[0]:
                    Free_List_Updating[0] = goods_list[0]
            for goods in goods_list[1]:
                with m_Updating:
                    Free_List_Updating[1].append(goods)
    with m_TotalThread:
        Totalthread_ThisTurn -= 1
        if Totalthread_ThisTurn <= 0:
            with m_Updating:
                Free_List[2] = time.strftime('%Y-%m-%d %H:%M:%S')
                Free_List[1] = []
                Free_List[0] = Free_List_Updating[0]
                for tmp_game in Free_List_Updating[1]:
                    tail = tmp_game[1].rfind("/?")
                    if tail != -1:
                        tmp_game[1] = tmp_game[1][0:tail]
                    flag_same = False
                    for game in Free_List[1]:
                        if game[1] == tmp_game[1]:
                            flag_same = True
                            break
                    if not flag_same:
                        Free_List[1].append(tmp_game)
            print("End Refreshing!")

def Refresh():
    '''
    Crawler
    '''
    global Free_List_Updating
    global Free_List
    global Totalthread_ThisTurn
    # Refreshing
    if Totalthread_ThisTurn > 0:
        print("One Task  Is Running, Please Wait...")
        return
    # Refresh over(Idle now)
    else:
        tryget = getFreeGoodsList(0)
        total_count = tryget[0]
        Free_List[2] += "(Refreshing now)"
        Free_List_Updating = [0, [], "0-0-0 0:0:0"]
    # calculate work of each thread and thread count
    n_page = math.ceil(total_count / 100)
    if n_page <= 10:
        n_thread = n_page
        n_perthread = 100
    else:
        n_perthread = math.ceil(n_page / 10)
        n_thread = math.ceil(n_page / n_perthread)
        n_perthread *= 100
    Totalthread_ThisTurn = n_thread
    print("Start Refreshing!")
    # mutithread
    threads = ThreadPoolExecutor(max_workers = n_thread)
    futures = [threads.submit(go_each, list(range(index, index + n_perthread, 100))) for index in list(range(0, total_count, n_perthread))]
    

RefreshKey = str(args.RefreshKey)

app = Flask(__name__)

@app.route("/api/freelist", methods = ["GET"])
def getFreeList():
    return jsonify({"total_count":Free_List[0], "free_list":Free_List[1], "update_time":Free_List[2]})

@app.route("/api/refresh", methods = ["POST"])
def postRefresh():
    if RefreshKey == request.values.get("pwd"):
        with m_TotalThread:
            if Totalthread_ThisTurn > 0:
                return "Task is Running!"
            else:
                Refresh()
                return "Submit successfully!"
    else:
        return "Pwd Wrong!"

@app.route("/", methods = ["GET"])
def index():
    return send_file("./index.html")

app.run(host='0.0.0.0', port=10001)
