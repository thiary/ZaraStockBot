from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
#from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import logging
import pickle
import telegram
import requests


class CZaraStockBot:
    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2

    def __init__(self):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

        self.updater = Updater(token='879329145:AAFotXv0ckFdlPctXn3SI-THxlH2Qwd3iK0')

        self.bot = telegram.Bot(token='879329145:AAFotXv0ckFdlPctXn3SI-THxlH2Qwd3iK0')

        self.datalist = []
        self.dataset = [' ', ' ', 0]
        self.insertmode = 0
        self.interval = 600

        try:
            with open('save.dat', 'rb') as f:
                self.datalist = pickle.load(f)
                f.close()
        except FileNotFoundError:
            pass

        self.dispatcher = self.updater.dispatcher
        self.dispatcher.add_handler( CommandHandler( 'show', self.cmdshow ) )
        self.dispatcher.add_handler( CommandHandler( 'del', self.cmddel ) )
        self.dispatcher.add_handler( CommandHandler( 'delall', self.cmddelall ) )
        self.dispatcher.add_handler( CommandHandler( 'save', self.cmdsave ) )
        self.dispatcher.add_handler( CommandHandler( 'help', self.cmdhelp ) )
        self.dispatcher.add_handler( CommandHandler( 'start', self.cmdstart ) )
        self.dispatcher.add_handler( CommandHandler( 'stop', self.cmdstop ) )
        self.dispatcher.add_handler( CommandHandler( 'interval', self.cmdinterval ) )
        self.updater.start_polling()

        echo_handler = MessageHandler(Filters.text, self.echo)
        self.dispatcher.add_handler(echo_handler)

        self.sched = BackgroundScheduler()
        self.sched.start()

    def cmdshow(self, bot, update):
        if len(self.datalist) == 0:
            bot.send_message(chat_id=update.message.chat_id, text='데이터가 없습니다.')
            return
        for data in self.datalist:
            bot.send_message(chat_id=data[2], text=data[0])
            bot.send_message(chat_id=data[2], text=data[1])

    def cmddel(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='삭제할 주소를 입력하세요')
        self.insertmode = 1

    def deldata(self, chat_id, url):
        deleted = False
        for data in self.datalist:
            if data[0] == url and data[2] == chat_id:
                del self.datalist[self.datalist.index( data )]
                deleted = True
        self.insertmode = 0
        return deleted

    def cmddelall(self, bot, update):
        self.datalist.clear()
        bot.send_message(chat_id=update.message.chat_id, text='모두 삭제되었습니다.')


    def cmdsave(self, bot, update):
        with open('save.dat', 'wb') as f:
            pickle.dump(self.datalist, f)
            f.close()
        bot.send_message(chat_id=update.message.chat_id, text='저장했습니다.')

    def cmdhelp(self, bot, update):
        msg = '사용법 \n1. 웹브라우져에서 재고확인을 하고자하는 하는 상품페이지로 이동\n2. 해당 상품의 url를 복사하여 채팅창에 입력\n3. 사이즈를 입력하세요 메시지가 출력\n4. 웹페이지에서 사이즈를 드래그하여 선택하고 복사하여 채팅창에 입력\n5. 현재 재고 확인후 재고확인목록에 추가됨'
        bot.send_message(chat_id=update.message.chat_id, text=msg)
        msg = '/show   모든 재고확인목록 출력\n/del    url과 사이즈로 하나의 재고확인목록 삭제\n/delall 모든 재고확인목록 삭제\n/save   현재 재고확인목록을 파일로 저장(서버에)\n/help   도움말\n/start  재고확인시작\n/stop   재고확인종료\n/interval 재고확인 간격을 설정합니다.'
        bot.send_message( chat_id=update.message.chat_id, text=msg )

    def cmdstart(self, bot, update):
        if len(self.datalist) != 0:
            msg = str(self.interval) + '초 간격으로 재고확인을 시작합니다.'
            self.sched.pause()
            self.sched.add_job( self.job_crawling, 'interval', seconds=self.interval)
            self.sched.resume()
        else:
            msg = '재고확인목록이 비었습니다. \n재고확인을 시작하지 않습니다.'
        bot.send_message( chat_id=update.message.chat_id, text=msg )


    def cmdstop(self, bot, update):
        if self.sched.state == self.STATE_RUNNING:
            msg = '재고확인을 정지합니다.'
            bot.send_message( chat_id=update.message.chat_id, text=msg )
            self.remove()
        else:
            msg = '재고확인중이 아닙니다.'
            bot.send_message( chat_id=update.message.chat_id, text=msg )


    def remove(self):
        if self.sched.state == self.STATE_RUNNING:
            self.sched.pause()
            self.sched.remove_all_jobs()


    def cmdinterval(self, bot, update):
        self.remove()
        self.insertmode = 2
        bot.send_message( chat_id=update.message.chat_id, text='재고확인 간격을 입력하세요' )

    def echo(self, bot, context):
        if self.insertmode == 2:
            self.interval = int(context.message.text.strip())
            bot.send_message( chat_id=context.message.chat_id, text='재고확인을 시작하시려면 /start를 입력하세요' )
        elif context.message.text.find('http') == 0:
            self.remove()
            if self.insertmode == 0:
                self.dataset = [' ', ' ', 0]
                self.dataset[0] = context.message.text.strip()
                bot.send_message(chat_id=context.message.chat_id, text='사이즈를 입력하세요')
            elif self.insertmode == 1:
                if self.deldata(context.message.chat_id, context.message.text.strip()):
                    bot.send_message(chat_id=context.message.chat_id, text='삭제되었습니다.')
                else:
                    bot.send_message(chat_id=context.message.chat_id, text='삭제될 내용이 없습니다.')
            else:
                bot.send_message(chat_id=context.message.chat_id, text='잘못입력하였습니다.')
        elif context.message.text.find('KR') != -1:
            self.dataset[1] = context.message.text.strip()
            self.dataset[2] = context.message.chat_id
            bot.send_message(chat_id=context.message.chat_id, text=context.message.text.strip() + '의 현재재고확인중입니다')
            product_name = self.check_stock(self.dataset, 0)
            if len(product_name) == 0:
                msg = product_name + ' ' + self.dataset[1] + '이 추가되지 않습니다..'
            else:
                self.datalist.insert(len(self.datalist), self.dataset[:])
                msg = product_name + ' ' + self.dataset[1] + '이 추가되었습니다. \n 재고확인을 시작하시려면 /start를 입력하세요'
            bot.send_message(chat_id=context.message.chat_id, text=msg)

    def job_crawling(self):
        for data in self.datalist:
            self.check_stock(data)

    def check_stock(self, data, mode=1):
        html = requests.get(data[0])
        size = data[1]
        usr = data[2]
        soup = BeautifulSoup(html.text, 'html.parser')
        tag = soup.find(value=size)
        product_name = ''

        if tag:
            disable = False
            for attr in tag.attrs:
                if 'disabled' == attr:
                    disable = True

            if disable and mode == 0:
                self.bot.send_message(chat_id=usr, text=size + '의 재고가 없습니다.')
                product_name = soup.find( 'h1' ).next
            elif disable == False:
                self.bot.send_message(chat_id=usr, text=data[0])
                self.bot.send_message(chat_id=usr, text=size + '의 재고가 있습니다.')
        else:
            self.bot.send_message(chat_id=usr, text='주소가 잘못되었습니다.')

        return product_name


jarabot = CZaraStockBot()
