import discord, requests, os, random, datetime, sys, psycopg2, urllib, json, time, re
from bs4 import BeautifulSoup
from discord.ext import tasks

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
NICO_EMAIL = os.environ.get('NICO_EMAIL')
NICO_PASSWD = os.environ.get('NICO_PASSWD')
DATABASE_URL = os.environ.get('DATABASE_URL')

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
client = discord.Client(intents=intents)

headers = {"User-Agent": "NicomuNotify/v0.0.1@Negima1072"}
ses = requests.session()
ses.headers = headers
res = ses.post("https://account.nicovideo.jp/api/v1/login", params={"mail_tel":NICO_EMAIL, "password":NICO_PASSWD}, headers={"Content-Type":"x-www-form-urlencoded"})
if res.headers["x-niconico-authflag"]==0:
    print("Error: Failed Niconico Login")
    sys.exit(1)

inv_mes = """招待ありがとうございます。`-nn setup`でセットアップができます。また`-nn help`でヘルプメッセージを表示できます。
Thank you for the invitation. You can set it up with `-nn setup`. You can also use `-nn help` to display help messages."""

help_mes_ja = """**-nn setup**
質問形式でこのBotのセットアップをします。
**-nn remove**
このサーバーに登録された情報を一度削除します。
**-nn status**
サーバーに登録されている情報を表示します。
**-nn help (ja/en)**
ヘルプメッセージを表示します。
**-nn author**
制作者情報を表示します。
"""

help_mes_en = """**-nn setup**
Set up this Bot in the form of a question.
**-nn remove**
Deletes the information registered on this server once.
**-nn status**
Displays the information registered with the server.
**-nn help (ja/en)**
Displays a help message.
**-nn author**
Displays the creator information.
"""

def getCommunityInfo(communityId):
    p=BeautifulSoup(ses.get("https://com.nicovideo.jp/community/"+communityId, headers=headers).text, "html.parser")
    title=p.find("h2", {"class":"title"}).find("a").get_text().replace("\t","").replace("\n","")
    comurl="https://com.nicovideo.jp/community/"+communityId
    imgurl="https://secure-dcdn.cdn.nimg.jp/comch/community-icon/128x128/"+communityId+".jpg"
    owner=p.find("th", text="オーナー").parent.find("td").find("a").get_text().replace("\t","").replace("\n","")
    ownerurl=p.find("th", text="オーナー").parent.find("td").find("a").get("href")
    openday=p.find("th", text="開設日").parent.find("td").get_text()
    level=p.find("dl", {"class":"communityScale"}).find("dd").get_text()
    member=p.find("dl", {"class":"communityScale"}).find_all("dd")[1].get_text().replace("\t","").replace("\n","")
    return {
        "title":title,
        "comurl":comurl,
        "imgurl":imgurl,
        "owner":owner,
        "ownerurl":ownerurl,
        "openday":openday,
        "level":level,
        "member":member,
    }

def communityEmbed(communityId):
    dt = getCommunityInfo(communityId)
    d="**Owner** "+"["+dt["owner"]+"]("+dt["ownerurl"]+")\n"
    d+="**CommunityID** ["+communityId+"]("+dt["comurl"]+")\n"
    d+="**Open** "+dt["openday"]+"\n"
    d+="**Level** "+dt["level"]+"\n"
    d+="**Member** "+dt["member"]
    embed = discord.Embed(title=dt["title"], description=d)
    embed.set_thumbnail(url=dt["imgurl"])
    return embed

def getCommunityBBSLastres(communityId):
    h = ses.get("https://com.nicovideo.jp/community/"+communityId, headers=headers).text
    hashcode = h[h.index("var NicommunityBBSHash = \"")+26:h.index("\";",h.index("var NicommunityBBSHash = \""))]
    res = ses.get("https://dic.nicovideo.jp/b/c/"+communityId+"/?com_header=1&hash_key="+hashcode, headers=headers)
    pas = BeautifulSoup(res.text, "html.parser")
    dl = pas.find("div", {"class":"community-bbs"}).find("dl")
    heads = dl.find_all("dt",{"class":"reshead"})
    bodys = dl.find_all("dd",{"class":"resbody"})
    if len(heads) == 0 or len(bodys) == 0:
        return 0
    else:
        return int(heads[-1].find("a").get("name"))

def getCommunityBBSComments(communityId, _from):
    if _from <= 0:
        return []
    lastres = getCommunityBBSLastres(communityId)
    if lastres < _from:
        return []
    resfrom = int(_from)
    if int(_from) % 30 != 1:
        resfrom = 30 * int(_from / 30) + 1
    comments = []
    h = ses.get("https://com.nicovideo.jp/community/"+communityId, headers=headers).text
    hashcode = h[h.index("var NicommunityBBSHash = \"")+26:h.index("\";",h.index("var NicommunityBBSHash = \""))]
    while True:
        res = ses.get("https://dic.nicovideo.jp/b/c/"+communityId+"/"+str(resfrom)+"-?com_header=1&hash_key="+hashcode, headers=headers)
        if res.status_code == 404:
            break
        pas = BeautifulSoup(res.text, "html.parser")
        dl = pas.find("div", {"class":"community-bbs"}).find("dl")
        heads = dl.find_all("dt",{"class":"reshead"})
        bodys = dl.find_all("dd",{"class":"resbody"})
        if len(heads) == 0 or len(bodys) == 0:
            break
        for i in range(len(heads)):
            if int(heads[i].find("a").get("name")) >= _from:
                for m in bodys[i].select("br"):
                    m.replace_with("\n")
                for m in bodys[i].select("iframe"):
                    m.replace_with("")
                bodyt = bodys[i].text.strip()
                while True:
                    if len(re.findall(">>sm\d{1,10}", bodyt)) > 0:
                        smid = re.findall(">>sm\d{1,10}", bodyt)[0]
                        bodyt=bodyt.replace(smid, "["+smid+"](https://www.nicovideo.jp/watch/"+smid[2:])
                    elif len(re.findall(">>co\d{1,10}", bodyt)) > 0:
                        smid = re.findall(">>co\d{1,10}", bodyt)[0]
                        bodyt=bodyt.replace(smid, "["+smid+"](https://com.nicovideo.jp/community/"+smid[2:])
                    else:
                        break
                comment = {
                    "no": int(heads[i].find("a").get("name")),
                    "text": str(bodyt),
                    "name": str(heads[i].find("span", {"class":"name"}).get_text()),
                    "id": str(heads[i].text[heads[i].text.index("ID: ")+4:-3]),
                    "date": str(re.findall(r"\d{4}/\d{2}/\d{2}\(.\) .{8}", heads[i].text)[0])
                }
                comments.append(comment)
        resfrom+=30
    return comments

def getCommunityMovieLastres(communityId):
    res = ses.get("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/contents/videos.json?limit=999&offset=0&sort=c&direction=d", headers=headers).json()
    if res["meta"]["status"] == 200:
        if res["data"]["total"] == 0:
            return 0
        else:
            return res["data"]["contents"][0]["id"]
    return 0

def getCommunityMovies(communityId, _from):
    res = ses.get("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/contents/videos.json?limit=999&offset=0&sort=c&direction=d", headers=headers).json()
    if res["meta"]["status"] == 200:
        if res["data"]["total"] != 0:
            movies=[]
            for i in range(len(res["data"]["contents"])):
                mv = res["data"]["contents"][len(res["data"]["contents"])-i-1]
                if mv["id"] >= _from:
                    res2=ses.get("https://www.nicovideo.jp/watch/"+mv["content_id"], headers=headers)
                    soup=BeautifulSoup(res2.text, "html.parser")
                    a=json.loads(soup.find_all("div", attrs={"id": "js-initial-watch-data"})[0].get("data-api-data"))
                    movie={
                        "id": mv["id"],
                        "smid": mv["content_id"],
                        "smurl": "https://www.nicovideo.jp/watch/"+mv["content_id"],
                        "title": a["video"]["originalTitle"],
                        "desc": a["video"]["originalDescription"],
                        "thumburl": a["video"]["thumbnailURL"],
                        "post": a["video"]["postedDateTime"],
                        "view": mv["cached_view_count"],
                        "comment": mv["cached_comment_count"],
                        "mylist": mv["cached_mylist_count"],
                        "ownerid": str(a["owner"]["id"]),
                        "ownername": a["owner"]["nickname"],
                        "adderid": str(mv["user_id"])
                    }
                    movies.append(movie)
            return movies
    return []

def liveStatus(t):
    if t == "RELEASED": return 0
    elif t == "ON_AIR": return 1
    elif t == "ENDED":  return 2
    else:               return 3

def getCommunityLiveLastres(communityId):
    res = ses.get("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/lives.json?limit=50&offset=0", headers=headers).json()
    if res["meta"]["status"] == 200:
        if len(res["data"]["lives"]) >= 1:
            return (int(res["data"]["lives"][0]["id"][2:]), liveStatus(res["data"]["lives"][0]["status"]))
    return (0, 2)

def getCommunityLives(communityId, _from):
    res = ses.get("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/lives.json?limit=50&offset=0", headers=headers).json()
    if res["meta"]["status"] == 200:
        if len(res["data"]["lives"]) >= 1:
            lives=[]
            for i in range(len(res["data"]["lives"])):
                lv = res["data"]["lives"][len(res["data"]["lives"])-i-1]
                if int(lv["id"][2:]) >= _from:
                    live={
                        "id": lv["id"],
                        "id_i": int(lv["id"][2:]),
                        "title": lv["title"],
                        "desc": lv["description"],
                        "status": lv["status"],
                        "status_i": liveStatus(lv["status"]),
                        "url": lv["watch_url"],
                        "comthumb_url": "https://secure-dcdn.cdn.nimg.jp/comch/community-icon/128x128/"+communityId+".jpg",
                        "ownername": ses.get("https://api.live2.nicovideo.jp/api/v1/user/nickname?userId="+str(lv["user_id"]), headers=headers).json()["data"]["nickname"],
                        "ownerid": str(lv["user_id"]),
                        "start": lv["started_at"],
                        "timeshift": lv["timeshift"]["enabled"],
                        "memberonly": lv["features"]["is_member_only"]
                    }
                    lives.append(live)
            return lives
    return []

def LiveEmbed(lv):
    d="**lvID** ["+lv["id"]+"]("+lv["url"]+")\n"
    d+="**投稿者** "+lv["ownername"]+"\n"
    d+="**開始時刻** "+datetime.datetime.strptime(lv["started_at"], '%Y-%m-%dT%H:%M:%S%z').strftime("%Y年%m月%d日 %H時%M分")+"\n"
    if lv["status_i"] == 2: d+="**開始時刻** "+datetime.datetime.strptime(lv["finished_at"], '%Y-%m-%dT%H:%M:%S%z').strftime("%Y年%m月%d日 %H時%M分")+"\n"
    embed = discord.Embed(title=lv["title"],description=d)
    embed.set_author(name=("新しい生放送が予約されました" if lv["status_i"] == 0 else "新しい生放送が開始されました" if lv["status_i"] == 1 else "生放送が終了しました"))
    embed.set_thumbnail(url=lv["comthumb_url"])
    return embed

def CommentEmbed(comment):
    d="**No."+str(comment["no"])+"** ： **"+comment["name"]+"**("+comment["id"]+")"
    embed = discord.Embed(description=d+"\n"+comment["text"])
    embed.set_author(name="新しいメッセージがありました")
    embed.set_footer(text=comment["date"])
    return embed

def MovieEmbed(movie):
    d="**smID** ["+movie["smid"]+"]("+movie["smurl"]+")\n"
    d+="**投稿者** "+movie["ownername"]+"\n"
    d+="**再生数** "+str(movie["view"])+"\n"
    d+="**コメント数** "+str(movie["comment"])+"\n"
    d+="**マイリスト数** "+str(movie["mylist"])+"\n"
    embed = discord.Embed(title=movie["title"],description=d)
    embed.set_author(name="新しい動画が登録されました")
    embed.set_footer(text="Added by "+ses.get("https://api.live2.nicovideo.jp/api/v1/user/nickname?userId="+movie["adderid"]).json()["data"]["nickname"])
    embed.set_thumbnail(url=movie["thumburl"])
    return embed

@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game(name='NicomuNotify | -nn help', start=datetime.datetime.now()))
    searching_10minutes_job.start()
    print("On Login")

@client.event
async def on_guild_join(guild):
    if guild.system_channel is not None:
        ch = guild.system_channel
    else:
        ch = guild.text_channels[0]
    await ch.send(inv_mes)
    return

@client.event
async def on_message(mes):
    if mes.author.bot:
        return
    if "-nn" in mes.content:
        try:
            param = mes.content.split()
            if len(param) < 2:
                return
            if param[1] == "help":
                if len(param) >= 3:
                    if param[2] == "en":
                        embed = discord.Embed(title="**HowtoUse**", description=help_mes_en)
                    else:
                        embed = discord.Embed(title="**使い方**", description=help_mes_ja)
                else:
                    embed = discord.Embed(title="**使い方**", description=help_mes_ja)
                member = mes.guild.get_member(int(mes.author.id))
                embed.set_footer(text="Requeted by "+member.display_name)
                await mes.channel.send(embed=embed)
                return
            if param[1] == "author":
                embed = discord.Embed(description="**Made by Negima1072**\n[Twitter](https://twitter.com/Negima1072)")
                await mes.channel.send(embed=embed)
                return
            if param[1] == "remove":
                with psycopg2.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE from guilds where guildId = %s", (str(mes.guild.id),))
                    conn.commit()
                    await mes.channel.send("このサーバーの設定は削除されました。\n再度開始するには`-nn setup`よりセットアップをしてください。")
                    return
            if param[1] == "status":
                with psycopg2.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT communityId,channelId,isMember from guilds where guildId = %s",(str(mes.guild.id),))
                        t = cur.fetchone()
                        (cid, chid, ism, )=(None, None, None) if t is None else t
                        member = mes.guild.get_member(int(mes.author.id))
                        embed = discord.Embed(title="Status", description="**Running** "+(":x:" if ism is None else ":white_check_mark:" if ism == 1 else ":x:")+"\n**CommunityID** "+(str(cid) if cid is not None else "null")+"\n**Channel** "+("<#"+str(chid)+">" if chid is not None else "null")+" \n**isCommuMember** "+(":x:" if ism is None else (":white_check_mark:" if ism == 1 else ":x:" if ism == 0 else ":regional_indicator_w:")))
                        embed.set_footer(text="Requeted by "+member.display_name)
                        await mes.channel.send(embed=embed)
                        if cid is not None and ism == 1:
                            await mes.channel.send(embed=communityEmbed(str(cid)))
                        return
                return
            if param[1] == "setup":
                if len(param) == 2:
                    with psycopg2.connect(DATABASE_URL) as conn:
                        with conn.cursor() as cur:
                            cur.execute("select count(*) from guilds where guildId = %s",(str(mes.guild.id),))
                            (count,) = cur.fetchone()
                            if count != 0:
                                await mes.channel.send("すでにこのサーバーは登録されている可能性があります。一度`-nn remove`で情報を削除後お試しください。")
                                return
                    with psycopg2.connect(DATABASE_URL) as conn:
                        with conn.cursor() as cur:
                            cur.execute("INSERT INTO guilds(guildId) VALUES(%s)", (str(mes.guild.id),))
                        conn.commit()
                        await mes.channel.send(f"{mes.author.mention} 最初に、連携するコミュニティーのURLかID(co~~~)を以下の形式で送信してください。\n`-nn setup com [url/id]`")
                        return
                    await mes.channel.send("エラーが発生した可能性があります。少し時間を開けたあと再度お試しください。それでも治らない場合は文末の文字列を明記の上制作者に連絡してください。[**SQLS2**]")
                    return
                if len(param) == 4:
                    if param[2] == "com":
                        communityId = param[3] if param[3].startswith("co") else urllib.parse.urlparse(param[3]).path.split("/")[-1]
                        with psycopg2.connect(DATABASE_URL) as conn:
                            with conn.cursor() as cur:
                                cur.execute("select count(*) from guilds where guildId = %s",(str(mes.guild.id),))
                                (count,) = cur.fetchone()
                                if count != 1:
                                    await mes.channel.send("途中からは開始できません。`-nn setup`ではじめからセットアップを開始してください。")
                                    return
                        with psycopg2.connect(DATABASE_URL) as conn:
                            with conn.cursor() as cur:
                                cur.execute("UPDATE guilds set communityId = %s where guildId = %s",(communityId, str(mes.guild.id)))
                            conn.commit()
                            await mes.channel.send(f"{mes.author.mention} 次に、通知を送信するチャンネルを、以下の形式で#から始まるチャンネル名かチャンネルIDで送信してください。\n`-nn setup ch [#name/id]`")
                            return
                        await mes.channel.send("エラーが発生した可能性があります。少し時間を開けたあと再度お試しください。それでも治らない場合は文末の文字列を明記の上制作者に連絡してください。[**SQLS3**]")
                        return
                    if param[2] == "ch":
                        channelId = param[3][2:-1] if param[3].startswith("<#") else str(int(param[3]))
                        with psycopg2.connect(DATABASE_URL) as conn:
                            with conn.cursor() as cur:
                                cur.execute("select count(*) from guilds where guildId = %s",(str(mes.guild.id),))
                                (count,) = cur.fetchone()
                                if count != 1:
                                    await mes.channel.send("途中からは開始できません。`-nn setup`ではじめからセットアップを開始してください。")
                                    return
                        with psycopg2.connect(DATABASE_URL) as conn:
                            with conn.cursor() as cur:
                                cur.execute("UPDATE guilds set channelId = %s where guildId = %s",(channelId, str(mes.guild.id)))
                            conn.commit()
                            with conn.cursor() as cur:
                                cur.execute("SELECT communityId from guilds where guildId = %s",(str(mes.guild.id),))
                                (communityId,) = cur.fetchone()
                                #Follow Community
                                headercomm = headers
                                headercomm["Referer"] = "https://com.nicovideo.jp/motion/"+communityId
                                headercomm["X-Requested-By"] = "https://com.nicovideo.jp/motion/"+communityId
                                headercomm["Accept"] = "application/json, text/plain, */*"
                                headercomm['Content-type']= 'application/json;charset=utf-8'
                                cres=ses.post("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/follows.json", headers=headers).json()
                                if cres["meta"]["status"] == 409:
                                    await mes.channel.send("すでに通知取得用のニコニコアカウントがすでにコミュニティーをフォローしていたようです。掲示板に新しいメッセージが来たら通知されるでしょう。")
                                    await mes.channel.send("**Congratulations！これで設定は完了です。**")
                                    await mes.guild.get_channel(int(channelId)).send(embed=communityEmbed(str(communityId)))
                                    lastres = getCommunityBBSLastres(str(communityId))
                                    lastmv = getCommunityMovieLastres(str(communityId))
                                    (lastlv,lvstatus) = getCommunityLiveLastres(str(communityId))
                                    with conn.cursor() as cur:
                                        cur.execute("UPDATE guilds set isMember = 1, lastres = %s, lastmv = %s, lastlv = %s, livestatus = %s where guildId = %s", (str(lastres),str(lastmv),str(lastlv),str(lvstatus),str(mes.guild.id)))
                                    conn.commit()
                                    return
                                elif cres["meta"]["status"] == 403:
                                    cres = ses.post("https://com.nicovideo.jp/api/v1/communities/"+communityId[2:]+"/follows/requests.json", headers=headercomm, data=json.dumps({"title":"DiscordBotのニコミュ通知くんです！","comment":"利用を開始するにはフォローリクエストを承認してください！","notify":False})).json()
                                    if cres["meta"]["status"] == 200:
                                        await mes.channel.send("お使いのコミュニティーがプライベートコミュニティーのためコミュニティーを通知取得用のニコニコアカウントがフォロー申請を送信しました。受理してください。\nhttps://com.nicovideo.jp/group_contact/"+communityId+"/"+str(cres["data"]["id"]))
                                        with conn.cursor() as cur:
                                            cur.execute("UPDATE guilds set isMember = %s where guildId = %s", (str(cres["data"]["id"]),str(mes.guild.id)))
                                        conn.commit()
                                        return
                                    elif cres["meta"]["status"] == 409:
                                        cur.execute("SELECT communityId,isMember from guilds where guildId = %s",(str(mes.guild.id),))
                                        (communityId,isMember,) = cur.fetchone()
                                        if isMember == 1:
                                            await mes.channel.send("すでにセットアップが終了しています。変更がある場合は`-nn remove`で情報を削除した後`-nn setup`でセットアップを開始してください。")
                                            return
                                        if isMember != 0:
                                            cres = ses.get("https://com.nicovideo.jp/api/v1/communities/follows/requests/"+str(isMember)+".json", headers=headers).json()
                                            if cres["meta"]["status"] == 200:
                                                if cres["data"]["follow_request"]["status"] == "accept":
                                                    cres=ses.put("https://com.nicovideo.jp/api/v1/communities/"+str(communityId)[2:]+"/follows/requests/"+str(isMember)+".json", headers=headers, data=json.dumps({"mode":"CLOSE"})).json()
                                                    if cres["meta"]["status"] == 200:
                                                        await mes.channel.send("コミュニティーのフォロー申請が受理されました。掲示板に新しいメッセージが来たら通知されるでしょう。")
                                                        await mes.channel.send("**Congratulations！これで設定は完了です。**")
                                                        await mes.guild.get_channel(int(channelId)).send(embed=communityEmbed(str(communityId)))
                                                        lastres = getCommunityBBSLastres(str(communityId))
                                                        lastmv = getCommunityMovieLastres(str(communityId))
                                                        (lastlv,lvstatus) = getCommunityLiveLastres(str(t[1]))
                                                        with conn.cursor() as cur:
                                                            cur.execute("UPDATE guilds set isMember = 1, lastres = %s, lastmv = %s, lastlv = %s, livestatus = %s where guildId = %s", (str(lastres),str(lastmv),str(lastlv),str(lvstatus),str(mes.guild.id)))
                                                        conn.commit()
                                                        return
                                        if isMember == 0:
                                            await mes.channel.send("すでに通知取得用のニコニコアカウントがすでにコミュニティーをフォローしていたようです。掲示板に新しいメッセージが来たら通知されるでしょう。")
                                            await mes.channel.send("**Congratulations！これで設定は完了です。**")
                                            await mes.guild.get_channel(int(channelId)).send(embed=communityEmbed(str(communityId)))
                                            lastres = getCommunityBBSLastres(str(communityId))
                                            lastmv = getCommunityMovieLastres(str(communityId))
                                            (lastlv,lvstatus) = getCommunityLiveLastres(str(communityId))
                                            with conn.cursor() as cur:
                                                cur.execute("UPDATE guilds set isMember = 1, lastres = %s, lastmv = %s, lastlv = %s, livestatus = %s where guildId = %s", (str(lastres),str(lastmv),str(lastlv),str(lvstatus),str(mes.guild.id)))
                                            conn.commit()
                                            return
                                        await mes.channel.send("お使いのコミュニティーがプライベートコミュニティーのためコミュニティーを通知取得用のニコニコアカウントがフォロー申請を送信しています。受理してください。")
                                        return
                                    else:
                                        print(cres)
                                        await mes.channel.send("エラーが発生した可能性があります。少し時間を開けたあと再度お試しください。それでも治らない場合は文末の文字列を明記の上制作者に連絡してください。[**COMF1**]")
                                        return
                                elif cres["meta"]["status"] == 200:
                                    await mes.channel.send("コミュニティーを通知取得用のニコニコアカウントがフォローしました。掲示板に新しいメッセージが来たら通知されるでしょう。")
                                    await mes.channel.send("**Congratulations！これで設定は完了です。**")
                                    await mes.guild.get_channel(int(channelId)).send(embed=communityEmbed(str(communityId)))
                                    lastres = getCommunityBBSLastres(str(communityId))
                                    lastmv = getCommunityMovieLastres(str(communityId))
                                    (lastlv,lvstatus) = getCommunityLiveLastres(str(communityId))
                                    with conn.cursor() as cur:
                                        cur.execute("UPDATE guilds set isMember = 1, lastres = %s, lastmv = %s, lastlv = %s, livestatus = %s where guildId = %s", (str(lastres),str(lastmv),str(lastlv),str(lvstatus),str(mes.guild.id)))
                                    conn.commit()
                                    return
                                else:
                                    print(cres)
                                    await mes.channel.send("エラーが発生した可能性があります。少し時間を開けたあと再度お試しください。それでも治らない場合は文末の文字列を明記の上制作者に連絡してください。[**COMF2**]")
                                    return
                        await mes.channel.send("エラーが発生した可能性があります。少し時間を開けたあと再度お試しください。それでも治らない場合は文末の文字列を明記の上制作者に連絡してください。[**SQLS4**]")
                        return
        except Exception as e:
            errorno = random.randint(10000,99999)
            print("["+str(errorno)+"]"+str(e))
            import traceback
            traceback.print_exc()
            await mes.channel.send("Something occurred error. **["+str(errorno)+"]**")
            return

##Todo: 　15分単位でページを取得
@tasks.loop(seconds=300)
async def searching_10minutes_job():
    #flag ga 1ijyouno sanka kakunin
    print("Job task:"+str(datetime.datetime.now()))
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            #メンバーか
            cur.execute("SELECT * from guilds")
            ts = cur.fetchall()
            for t in ts:
                if t[4] == 1:
                    res = ses.get("https://com.nicovideo.jp/api/v1/communities/"+t[1][2:]+"/authority.json", headers=headers).json()
                    if res["meta"]["status"] == 200:
                        if not res["data"]["is_member"]:
                            #Join
                            guild=client.get_guild(t[0])
                            ch=guild.get_channel(t[2])
                            await ch.send("情報取得用のアカウントがコミュニティーのフォロワーでなくなっています。\n`-nn remove`から一度情報を削除し、`-nn setup`でセットアップをしてください。")
                            continue
                elif t[4] > 1:
                    res = ses.get("https://com.nicovideo.jp/api/v1/communities/follows/requests/"+str(t[4])+".json", headers=headers).json()
                    if res["meta"]["status"] == 200:
                        if res["data"]["follow_request"]["status"] == "accept":
                            #Cong
                            res=ses.put("https://com.nicovideo.jp/api/v1/communities/"+str(t[1])[2:]+"/follows/requests/"+str(t[4])+".json", headers=headers, data=json.dumps({"mode":"CLOSE"})).json()
                            if res["meta"]["status"] == 200:
                                guild=client.get_guild(t[0])
                                ch=guild.get_channel(t[2])
                                await ch.send("コミュニティーのフォロー申請が受理されました。掲示板に新しいメッセージが来たら通知されるでしょう。")
                                await ch.send("**Congratulations！これで設定は完了です。**")
                                await ch.send(embed=communityEmbed(str(t[1])))
                                lastres = getCommunityBBSLastres(str(t[1]))
                                lastmv = getCommunityMovieLastres(str(t[1]))
                                with conn.cursor() as cur:
                                    cur.execute("UPDATE guilds set isMember = 1, lastres = %s, lastmv = %s where guildId = %s", (str(lastres),str(lastmv),str(t[0])))
                                conn.commit()
                                continue
                        elif res["data"]["follow_request"]["status"] == "reject":
                            #Join
                            guild=client.get_guild(t[0])
                            ch=guild.get_channel(t[2])
                            await ch.send("情報取得アカウントのフォロー申請が拒否されました。\n`-nn remove`から一度情報を削除し、`-nn setup`でセットアップをしてください。")
                            continue
                        elif res["data"]["follow_request"]["status"] == "send":
                            #saisoku
                            guild=client.get_guild(t[0])
                            ch=guild.get_channel(t[2])
                            await ch.send("情報取得アカウントのフォロー申請を承諾してください。\nフォロー申請の承諾後このBotは使えるようになります。\nhttps://com.nicovideo.jp/group_contact/"+t[1]+"/"+str(t[4]))
                            continue
                    print(res)
                    print("Error[317]")
                time.sleep(0.1)
            #あたらいいコメント
            cur.execute("SELECT * from guilds")
            ts = cur.fetchall()
            for t in ts:
                if t[4] == 1:
                    #lastresと今の比較　更新されたぶんを送信
                    lastres = getCommunityBBSLastres(str(t[1]))
                    if t[3] < lastres:
                        #koushin
                        comments = getCommunityBBSComments(t[1], t[3]+1)
                        if len(comments) == 0:
                            continue
                        with conn.cursor() as cur:
                            cur.execute("UPDATE guilds set lastres = %s where guildId = %s", (str(comments[-1]["no"]), str(t[0])))
                        conn.commit()
                        guild=client.get_guild(t[0])
                        ch=guild.get_channel(t[2])
                        for c in comments:
                            await ch.send(embed=CommentEmbed(c))
                        continue
                    continue
                time.sleep(0.1)
            #あたらしい動画
            for t in ts:
                if t[4] == 1:
                    lastmv = getCommunityMovieLastres(str(t[1]))
                    if t[5] < lastmv:
                        movies = getCommunityMovies(t[1], t[5]+1);
                        if len(movies) == 0:
                            continue
                        with conn.cursor() as cur:
                            cur.execute("UPDATE guilds set lastmv = %s where guildId = %s", (str(movies[-1]["id"]), str(t[0])))
                        conn.commit()
                        guild=client.get_guild(t[0])
                        ch=guild.get_channel(t[2])
                        for m in movies:
                            await ch.send(embed=MovieEmbed(m))
                        continue
                    continue
                time.sleep(0.1)
            #あたらしい生放送
            for t in ts:
                if t[4] == 1:
                    (lastlv,lvstatus) = getCommunityLiveLastres(str(t[1]))
                    if t[6] < lastlv or t[7] < lvstatus:
                        lives = getCommunityLives(t[1], t[6]+1);
                        if len(lives) == 0:
                            continue
                        with conn.cursor() as cur:
                            cur.execute("UPDATE guilds set lastlv = %s, livestatus = %s where guildId = %s", (str(lives[-1]["id"][2:]),str(lives[-1]["status_i"]), str(t[0])))
                        conn.commit()
                        guild=client.get_guild(t[0])
                        ch=guild.get_channel(t[2])
                        for m in lives:
                            await ch.send(embed=LiveEmbed(m))
                        continue
                    continue
    return

client.run(ACCESS_TOKEN)