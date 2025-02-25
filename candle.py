import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import threading
import os
from colorama import init, Fore, Style, Back
from tabulate import tabulate

# colorama 초기화 (Windows에서도 색상 지원)
init()

class TelegramNotifier:
    def __init__(self, token, chat_id):
        """Telegram 봇 초기화"""
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, message):
        """텔레그램으로 메시지 전송 (requests 라이브러리 사용)"""
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                print(f"텔레그램 메시지 전송 성공: {message[:50]}...")
                return True
            else:
                print(f"텔레그램 메시지 전송 실패: HTTP {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"텔레그램 메시지 전송 오류: {e}")
            return False
            
    def send_pattern_alert(self, symbol, interval, timestamp, patterns):
        """패턴 알림 메시지 전송"""
        message = f"🔔 <b>{symbol} ({interval})</b> - 새로운 패턴 감지!\n"
        message += f"⏰ <b>시간:</b> {timestamp}\n\n"
        
        for pattern in patterns:
            # 신호에 따라 이모지 선택
            if "강세" in pattern['signal']:
                emoji = "🟢"
            elif "약세" in pattern['signal']:
                emoji = "🔴"
            else:
                emoji = "⚪"
                
            message += f"{emoji} <b>{pattern['name']}</b>\n"
            message += f"  • 신호: {pattern['signal']}\n"
        
        return self.send_message(message)

class CandlePatternDetector:
    def __init__(self):
        # 패턴 설명 추가
        self.pattern_descriptions = {
            'doji': {
                'name': '도지(Doji)',
                'description': '시가와 종가가 거의 같은 패턴. 시장의 불확실성을 나타내며, 현재 추세의 약화와 잠재적 반전 신호일 수 있습니다.',
                'signal': '중립 또는 현재 추세의 약화',
                'color': Fore.YELLOW
            },
            'hammer': {
                'name': '망치(Hammer)',
                'description': '작은 몸체와 긴 아래 그림자를 가진 패턴. 하락 추세의 끝에서 나타나면 반전 신호가 될 수 있습니다.',
                'signal': '하락 추세에서 나타나면 강세(상승) 신호',
                'color': Fore.GREEN
            },
            'inverted_hammer': {
                'name': '역망치(Inverted Hammer)',
                'description': '작은 몸체와 긴 위 그림자를 가진 패턴. 하락 추세의 끝에서 나타나면 반전 신호가 될 수 있습니다.',
                'signal': '하락 추세에서 나타나면 강세(상승) 신호',
                'color': Fore.GREEN
            },
            'bullish_engulfing': {
                'name': '강세 매몰(Bullish Engulfing)',
                'description': '하락 캔들 다음에 나타나는 더 큰 상승 캔들로, 이전 캔들을 완전히 감싸는 패턴.',
                'signal': '강한 강세(상승) 신호',
                'color': Fore.GREEN + Style.BRIGHT
            },
            'bearish_engulfing': {
                'name': '약세 매몰(Bearish Engulfing)',
                'description': '상승 캔들 다음에 나타나는 더 큰 하락 캔들로, 이전 캔들을 완전히 감싸는 패턴.',
                'signal': '강한 약세(하락) 신호',
                'color': Fore.RED + Style.BRIGHT
            },
            'morning_star': {
                'name': '모닝스타(Morning Star)',
                'description': '하락 추세의 끝에서 나타나는 3개의 캔들 패턴. 큰 하락 캔들, 작은 몸체의 캔들, 큰 상승 캔들로 구성됩니다.',
                'signal': '강한 강세(상승) 신호',
                'color': Fore.GREEN + Style.BRIGHT
            },
            'evening_star': {
                'name': '이브닝스타(Evening Star)',
                'description': '상승 추세의 끝에서 나타나는 3개의 캔들 패턴. 큰 상승 캔들, 작은 몸체의 캔들, 큰 하락 캔들로 구성됩니다.',
                'signal': '강한 약세(하락) 신호',
                'color': Fore.RED + Style.BRIGHT
            },
            'three_white_soldiers': {
                'name': '세 개의 백색 병사(Three White Soldiers)',
                'description': '연속된 3개의 상승 캔들로, 각 캔들의 시가가 이전 캔들의 몸체 내에서 시작되고 종가는 이전 캔들보다 높은 패턴.',
                'signal': '강한 강세(상승) 신호',
                'color': Fore.GREEN + Style.BRIGHT
            },
            'three_black_crows': {
                'name': '세 개의 검은 까마귀(Three Black Crows)',
                'description': '연속된 3개의 하락 캔들로, 각 캔들의 시가가 이전 캔들의 몸체 내에서 시작되고 종가는 이전 캔들보다 낮은 패턴.',
                'signal': '강한 약세(하락) 신호',
                'color': Fore.RED + Style.BRIGHT
            },
            'bullish_harami': {
                'name': '강세 하라미(Bullish Harami)',
                'description': '큰 하락 캔들 다음에 나타나는 작은 상승 캔들로, 이전 캔들의 몸체 내에 완전히 포함되는 패턴.',
                'signal': '약한 강세(상승) 신호',
                'color': Fore.GREEN
            },
            'bearish_harami': {
                'name': '약세 하라미(Bearish Harami)',
                'description': '큰 상승 캔들 다음에 나타나는 작은 하락 캔들로, 이전 캔들의 몸체 내에 완전히 포함되는 패턴.',
                'signal': '약한 약세(하락) 신호',
                'color': Fore.RED
            }
        }

    def get_candle_info(self, row):
        """캔들의 상세 정보 계산"""
        open_price = float(row['open'])
        high_price = float(row['high'])
        low_price = float(row['low'])
        close_price = float(row['close'])
        
        body_size = abs(close_price - open_price)
        total_size = high_price - low_price
        is_bullish = close_price > open_price
        
        upper_shadow = high_price - (close_price if is_bullish else open_price)
        lower_shadow = (open_price if is_bullish else close_price) - low_price
        
        return {
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'body_size': body_size,
            'total_size': total_size,
            'is_bullish': is_bullish,
            'upper_shadow': upper_shadow,
            'lower_shadow': lower_shadow
        }

    def is_doji(self, row):
        """도지(Doji) 패턴 탐지"""
        info = self.get_candle_info(row)
        return (info['body_size'] / info['total_size'] < 0.1 if info['total_size'] > 0 else False)

    def is_hammer(self, row):
        """망치(Hammer) 패턴 탐지"""
        info = self.get_candle_info(row)
        return (
            info['lower_shadow'] > 2 * info['body_size'] and
            info['upper_shadow'] < 0.1 * info['total_size'] and
            info['body_size'] > 0
        )

    def is_inverted_hammer(self, row):
        """역망치(Inverted Hammer) 패턴 탐지"""
        info = self.get_candle_info(row)
        return (
            info['upper_shadow'] > 2 * info['body_size'] and
            info['lower_shadow'] < 0.1 * info['total_size'] and
            info['body_size'] > 0
        )

    def is_bullish_engulfing(self, current_row, previous_row):
        """강세 매몰(Bullish Engulfing) 패턴 탐지"""
        current = self.get_candle_info(current_row)
        previous = self.get_candle_info(previous_row)
        
        return (
            current['is_bullish'] and
            not previous['is_bullish'] and
            current['open'] < previous['close'] and
            current['close'] > previous['open']
        )

    def is_bearish_engulfing(self, current_row, previous_row):
        """약세 매몰(Bearish Engulfing) 패턴 탐지"""
        current = self.get_candle_info(current_row)
        previous = self.get_candle_info(previous_row)
        
        return (
            not current['is_bullish'] and
            previous['is_bullish'] and
            current['open'] > previous['close'] and
            current['close'] < previous['open']
        )

    def is_morning_star(self, current_row, previous_row, pre_previous_row):
        """모닝스타(Morning Star) 패턴 탐지"""
        first = self.get_candle_info(pre_previous_row)
        middle = self.get_candle_info(previous_row)
        last = self.get_candle_info(current_row)
        
        return (
            not first['is_bullish'] and
            first['body_size'] > 0.5 * first['total_size'] and
            middle['body_size'] < 0.3 * middle['total_size'] and
            last['is_bullish'] and
            last['body_size'] > 0.5 * last['total_size'] and
            middle['close'] < first['close'] and
            middle['open'] < first['close'] and
            last['open'] > middle['close'] and
            last['close'] > (first['open'] + first['close']) / 2
        )

    def is_evening_star(self, current_row, previous_row, pre_previous_row):
        """이브닝스타(Evening Star) 패턴 탐지"""
        first = self.get_candle_info(pre_previous_row)
        middle = self.get_candle_info(previous_row)
        last = self.get_candle_info(current_row)
        
        return (
            first['is_bullish'] and
            first['body_size'] > 0.5 * first['total_size'] and
            middle['body_size'] < 0.3 * middle['total_size'] and
            not last['is_bullish'] and
            last['body_size'] > 0.5 * last['total_size'] and
            middle['close'] > first['close'] and
            middle['open'] > first['close'] and
            last['open'] < middle['close'] and
            last['close'] < (first['open'] + first['close']) / 2
        )

    def is_three_white_soldiers(self, current_row, previous_row, pre_previous_row):
        """세 개의 백색 병사(Three White Soldiers) 패턴 탐지"""
        first = self.get_candle_info(pre_previous_row)
        second = self.get_candle_info(previous_row)
        third = self.get_candle_info(current_row)
        
        return (
            first['is_bullish'] and
            second['is_bullish'] and
            third['is_bullish'] and
            first['body_size'] > 0.5 * first['total_size'] and
            second['body_size'] > 0.5 * second['total_size'] and
            third['body_size'] > 0.5 * third['total_size'] and
            second['open'] > first['open'] and
            second['close'] > first['close'] and
            third['open'] > second['open'] and
            third['close'] > second['close']
        )

    def is_three_black_crows(self, current_row, previous_row, pre_previous_row):
        """세 개의 검은 까마귀(Three Black Crows) 패턴 탐지"""
        first = self.get_candle_info(pre_previous_row)
        second = self.get_candle_info(previous_row)
        third = self.get_candle_info(current_row)
        
        return (
            not first['is_bullish'] and
            not second['is_bullish'] and
            not third['is_bullish'] and
            first['body_size'] > 0.5 * first['total_size'] and
            second['body_size'] > 0.5 * second['total_size'] and
            third['body_size'] > 0.5 * third['total_size'] and
            second['open'] < first['open'] and
            second['close'] < first['close'] and
            third['open'] < second['open'] and
            third['close'] < second['close']
        )

    def is_bullish_harami(self, current_row, previous_row):
        """강세 하라미(Bullish Harami) 패턴 탐지"""
        current = self.get_candle_info(current_row)
        previous = self.get_candle_info(previous_row)
        
        return (
            not previous['is_bullish'] and
            current['is_bullish'] and
            previous['body_size'] > current['body_size'] and
            current['open'] > previous['close'] and
            current['close'] < previous['open']
        )

    def is_bearish_harami(self, current_row, previous_row):
        """약세 하라미(Bearish Harami) 패턴 탐지"""
        current = self.get_candle_info(current_row)
        previous = self.get_candle_info(previous_row)
        
        return (
            previous['is_bullish'] and
            not current['is_bullish'] and
            previous['body_size'] > current['body_size'] and
            current['open'] < previous['close'] and
            current['close'] > previous['open']
        )

    def detect_patterns(self, df):
        """모든 패턴 확인"""
        results = []
        
        for i in range(len(df)):
            pattern_found = []
            current_row = df.iloc[i]
            
            # 단일 캔들 패턴 확인
            if self.is_doji(current_row):
                pattern_found.append('doji')
            if self.is_hammer(current_row):
                pattern_found.append('hammer')
            if self.is_inverted_hammer(current_row):
                pattern_found.append('inverted_hammer')
            
            # 다중 캔들 패턴 확인 (최소 2개 이상의 캔들 필요)
            if i >= 1:
                previous_row = df.iloc[i-1]
                
                if self.is_bullish_engulfing(current_row, previous_row):
                    pattern_found.append('bullish_engulfing')
                if self.is_bearish_engulfing(current_row, previous_row):
                    pattern_found.append('bearish_engulfing')
                if self.is_bullish_harami(current_row, previous_row):
                    pattern_found.append('bullish_harami')
                if self.is_bearish_harami(current_row, previous_row):
                    pattern_found.append('bearish_harami')
            
            # 3개 캔들 패턴 확인 (최소 3개 이상의 캔들 필요)
            if i >= 2:
                previous_row = df.iloc[i-1]
                pre_previous_row = df.iloc[i-2]
                
                if self.is_morning_star(current_row, previous_row, pre_previous_row):
                    pattern_found.append('morning_star')
                if self.is_evening_star(current_row, previous_row, pre_previous_row):
                    pattern_found.append('evening_star')
                if self.is_three_white_soldiers(current_row, previous_row, pre_previous_row):
                    pattern_found.append('three_white_soldiers')
                if self.is_three_black_crows(current_row, previous_row, pre_previous_row):
                    pattern_found.append('three_black_crows')
            
            if pattern_found:
                results.append({
                    'index': i,
                    'timestamp': current_row['timestamp'],
                    'patterns': pattern_found
                })
        
        return results

    def add_pattern_descriptions(self, results):
        """패턴 설명 추가"""
        for result in results:
            patterns_with_desc = []
            
            for pattern in result['patterns']:
                patterns_with_desc.append({
                    'pattern': pattern,
                    'name': self.pattern_descriptions[pattern]['name'],
                    'description': self.pattern_descriptions[pattern]['description'],
                    'signal': self.pattern_descriptions[pattern]['signal'],
                    'color': self.pattern_descriptions[pattern]['color']
                })
            
            result['patterns_with_desc'] = patterns_with_desc
            
        return results


class BinanceAPI:
    def __init__(self):
        self.base_url = 'https://api.binance.com/api/v3'
        self.time_intervals = {
            '1h': '1h',
            '4h': '4h',
            '1d': '1d',
            '1w': '1w'
        }

    def get_klines(self, symbol, interval, limit=1000):  # 1000개로 증가
        """캔들스틱 데이터 가져오기"""
        try:
            url = f"{self.base_url}/klines?symbol={symbol}&interval={interval}&limit={limit}"
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"HTTP 오류: {response.status_code}")
                return None
            
            data = response.json()
            
            # 데이터프레임으로 변환
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # 숫자 형식으로 변환
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 타임스탬프를 datetime으로 변환
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        
        except Exception as e:
            print(f"{symbol} {interval} 데이터 가져오기 오류:", e)
            return None

    def format_timestamp(self, timestamp):
        """타임스탬프를 한국 시간(KST)으로 변환"""
        if isinstance(timestamp, pd.Timestamp):
            # UTC에서 KST로 변환 (9시간 추가)
            korea_time = timestamp + pd.Timedelta(hours=9)
            return korea_time.strftime('%Y-%m-%d %H:%M:%S')
        return str(timestamp)


class CandlePatternApp:
    def __init__(self, telegram_token=None, telegram_chat_id=None):
        self.api = BinanceAPI()
        self.detector = CandlePatternDetector()
        self.symbols = ['BTCUSDT', 'SOLUSDT']
        self.intervals = ['1h', '4h', '1d', '1w']
        self.update_intervals = {
            '1h': 60 * 60,  # 1시간 (초 단위)
            '4h': 4 * 60 * 60,  # 4시간 (초 단위)
            '1d': 24 * 60 * 60,  # 1일 (초 단위)
            '1w': 7 * 24 * 60 * 60  # 1주 (초 단위)
        }
        self.last_update_time = {}
        self.last_pattern_time = {}
        self.is_first_run = True  # 최초 실행 확인 플래그
        
        # 텔레그램 봇 설정
        self.telegram = None
        if telegram_token and telegram_chat_id:
            try:
                self.telegram = TelegramNotifier(telegram_token, telegram_chat_id)
                print(f"{Fore.GREEN}텔레그램 봇이 성공적으로 연결되었습니다.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}텔레그램 봇 연결 오류: {e}{Style.RESET_ALL}")
        
        # 각 심볼 및 간격별 업데이트 시간 초기화
        for symbol in self.symbols:
            self.last_update_time[symbol] = {}
            self.last_pattern_time[symbol] = {}
            for interval in self.intervals:
                self.last_update_time[symbol][interval] = 0
                self.last_pattern_time[symbol][interval] = None
                
    def print_current_status(self, symbol, interval, current_patterns):
        """현재 캔들에서 감지된 패턴만 표시"""
        if not current_patterns:
            print(f"\n{symbol} ({interval}): 현재 캔들에서 감지된 패턴 없음")
            return
        
        title = f"{symbol} ({interval}) - 현재 상태"
        print(f"\n{Back.BLUE}{Fore.WHITE} {title} {Style.RESET_ALL}")
        
        table_data = []
        for pattern in current_patterns:
            color = pattern['color']
            table_data.append([
                f"{color}{pattern['name']}{Style.RESET_ALL}",
                f"{color}{pattern['signal']}{Style.RESET_ALL}"
            ])
        
        # 테이블 출력
        headers = ["패턴", "신호"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def fetch_data_if_needed(self, symbol, interval):
        """필요한 경우에만 데이터 가져오기"""
        current_time = time.time()
        last_update = self.last_update_time[symbol][interval]
        update_interval = self.update_intervals[interval]
        
        if current_time - last_update > update_interval:
            print(f"{Fore.CYAN}{symbol} {interval} 타임프레임에 대한 새 데이터 가져오는 중...{Style.RESET_ALL}")
            data = self.api.get_klines(symbol, interval)
            self.last_update_time[symbol][interval] = current_time
            return data
        else:
            print(f"{symbol} {interval} 타임프레임에 대한 캐시된 데이터 사용 중...")
            return None  # 업데이트가 필요하지 않음

    def filter_recent_data(self, df, interval):
        """최근 7일 이내 데이터만 필터링"""
        # 주봉은 모든 데이터 표시
        if interval == '1w':
            return df
            
        # 나머지 타임프레임은 최근 7일 데이터만 표시
        seven_days_ago = datetime.now() - timedelta(days=7)
        seven_days_ago = pd.Timestamp(seven_days_ago)
        
        # UTC 기준으로 7일 전 계산 (타임스탬프가 UTC 기준이므로)
        seven_days_ago_utc = seven_days_ago - pd.Timedelta(hours=9)
        
        # 최근 7일 데이터만 필터링
        filtered_df = df[df['timestamp'] >= seven_days_ago_utc]
        
        return filtered_df

    def detect_all_patterns(self):
        """모든 심볼 및 간격에 대한 패턴 감지"""
        all_results = []
        current_status = {}
        recent_patterns = {}
        
        for symbol in self.symbols:
            current_status[symbol] = {}
            recent_patterns[symbol] = {}
            
            for interval in self.intervals:
                try:
                    df = self.api.get_klines(symbol, interval)
                    if df is None or len(df) == 0:
                        continue
                    
                    # 최근 7일 데이터만 필터링 (주봉 제외)
                    recent_df = self.filter_recent_data(df, interval)
                    
                    # 전체 데이터에서 패턴 탐지
                    all_results_temp = self.detector.detect_patterns(df)
                    all_results_with_desc = self.detector.add_pattern_descriptions(all_results_temp)
                    
                    if len(all_results_with_desc) > 0:
                        # 현재 캔들 (마지막 캔들) 패턴
                        current_idx = len(df) - 1
                        current_patterns = [r for r in all_results_with_desc if r['index'] == current_idx]
                        
                        if current_patterns and len(current_patterns) > 0:
                            current_status[symbol][interval] = current_patterns[0]['patterns_with_desc']
                            
                            # 최초 실행이 아닐 때만 현재 패턴에 대한 알림 전송
                            if not self.is_first_run:
                                current_time = current_patterns[0]['timestamp']
                                if (self.telegram and 
                                    (symbol not in self.last_pattern_time or 
                                     interval not in self.last_pattern_time[symbol] or 
                                     self.last_pattern_time[symbol][interval] != current_time)):
                                    
                                    self.telegram.send_pattern_alert(
                                        symbol, 
                                        interval, 
                                        self.api.format_timestamp(current_time), 
                                        current_patterns[0]['patterns_with_desc']
                                    )
                                    self.last_pattern_time[symbol][interval] = current_time
                        else:
                            current_status[symbol][interval] = []
                        
                        # 최근 패턴 (마지막 10개 캔들 중 가장 최근 패턴)
                        recent_range = min(10, len(df))
                        recent_indices = range(len(df) - recent_range, len(df))
                        recent_results = [r for r in all_results_with_desc if r['index'] in recent_indices]
                        
                        if recent_results and len(recent_results) > 0:
                            # 인덱스가 큰 순서(최신순)으로 정렬
                            sorted_results = sorted(recent_results, key=lambda x: x['index'], reverse=True)
                            recent_patterns[symbol][interval] = {
                                'time': self.api.format_timestamp(sorted_results[0]['timestamp']),
                                'patterns': sorted_results[0]['patterns_with_desc'],
                                'timestamp': sorted_results[0]['timestamp']  # 원래 타임스탬프도 저장
                            }
                            
                            # 최초 실행 시 최근 패턴 기록 (중복 메시지 방지)
                            if self.is_first_run:
                                self.last_pattern_time[symbol][interval] = sorted_results[0]['timestamp']
                        else:
                            recent_patterns[symbol][interval] = None
                except Exception as e:
                    print(f"{symbol} {interval} 패턴 감지 중 오류: {e}")
        
        # 현재 캔들 상태 출력
        print(f'\n{Back.BLUE}{Fore.WHITE} 현재 캔들 상태 {Style.RESET_ALL}')
        for symbol in self.symbols:
            for interval in self.intervals:
                if symbol in current_status and interval in current_status[symbol]:
                    self.print_current_status(symbol, interval, current_status[symbol][interval])
        
        # 최근 패턴 출력
        print(f'\n{Back.BLUE}{Fore.WHITE} 최근 감지된 패턴 {Style.RESET_ALL}')
        for symbol in self.symbols:
            print(f"\n{Back.WHITE}{Fore.BLACK} {symbol} 최근 패턴 {Style.RESET_ALL}")
            table_data = []
            
            for interval in self.intervals:
                if symbol in recent_patterns and interval in recent_patterns[symbol] and recent_patterns[symbol][interval]:
                    patterns_str = []
                    for p in recent_patterns[symbol][interval]['patterns']:
                        patterns_str.append(f"{p['color']}{p['name']}{Style.RESET_ALL} ({p['color']}{p['signal']}{Style.RESET_ALL})")
                    
                    table_data.append([
                        interval,
                        recent_patterns[symbol][interval]['time'],
                        '\n'.join(patterns_str)
                    ])
                else:
                    table_data.append([
                        interval,
                        "없음",
                        "최근 패턴 없음"
                    ])
            
            # 테이블 출력
            headers = ["타임프레임", "시간 (KST)", "패턴 (신호)"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # 최초 실행 시에만 종합 요약 메시지 보내기
        if self.is_first_run and self.telegram:
            self.send_summary_message(recent_patterns)
            self.is_first_run = False
            
        return recent_patterns
        
    def send_summary_message(self, recent_patterns):
        """각 심볼별 최근 패턴 종합 요약 메시지 전송"""
        for symbol in self.symbols:
            summary_message = f"📊 <b>{symbol} 최근 패턴 요약</b>\n\n"
            has_patterns = False
            
            for interval in self.intervals:
                if symbol in recent_patterns and interval in recent_patterns[symbol] and recent_patterns[symbol][interval]:
                    has_patterns = True
                    pattern_info = recent_patterns[symbol][interval]
                    
                    # 타임프레임과 시간 정보 추가
                    summary_message += f"⏰ <b>{interval}</b> ({pattern_info['time']})\n"
                    
                    # 패턴 정보 추가
                    for p in pattern_info['patterns']:
                        # 신호에 따라 이모지 선택
                        if "강세" in p['signal']:
                            emoji = "🟢"
                        elif "약세" in p['signal']:
                            emoji = "🔴"
                        else:
                            emoji = "⚪"
                        
                        summary_message += f"{emoji} <b>{p['name']}</b> - {p['signal']}\n"
                    
                    summary_message += "\n"
            
            # 패턴이 있는 경우에만 메시지 전송
            if has_patterns:
                self.telegram.send_message(summary_message)
    
    def check_for_updates(self, symbol, interval):
        """주기적으로 업데이트 확인"""
        while True:
            try:
                data = self.fetch_data_if_needed(symbol, interval)
                
                if data is not None:
                    # 전체 데이터에서 패턴 탐지
                    all_results = self.detector.detect_patterns(data)
                    all_results_with_desc = self.detector.add_pattern_descriptions(all_results)
                    
                    # 현재 캔들 패턴만 확인
                    current_idx = len(data) - 1
                    current_patterns = [r for r in all_results_with_desc if r['index'] == current_idx]
                    
                    if current_patterns and len(current_patterns) > 0:
                        patterns = current_patterns[0]['patterns_with_desc']
                        timestamp = current_patterns[0]['timestamp']
                        
                        # 이전에 없던 새로운 패턴인지 확인
                        is_new_pattern = (
                            symbol not in self.last_pattern_time or 
                            interval not in self.last_pattern_time[symbol] or 
                            self.last_pattern_time[symbol][interval] != timestamp
                        )
                        
                        if patterns and is_new_pattern:
                            # 콘솔에 패턴 출력
                            title = f"{symbol} ({interval}) - 현재 캔들에서 새로운 패턴 감지!"
                            print(f"\n{Back.GREEN}{Fore.WHITE} {title} {Style.RESET_ALL}")
                            
                            table_data = []
                            for pattern in patterns:
                                color = pattern['color']
                                table_data.append([
                                    self.api.format_timestamp(timestamp),
                                    f"{color}{pattern['name']}{Style.RESET_ALL}",
                                    f"{color}{pattern['signal']}{Style.RESET_ALL}"
                                ])
                            
                            # 테이블 출력
                            headers = ["시간 (KST)", "패턴", "신호"]
                            print(tabulate(table_data, headers=headers, tablefmt="grid"))
                            
                            # 텔레그램 알림 전송
                            if self.telegram:
                                self.telegram.send_pattern_alert(
                                    symbol, 
                                    interval, 
                                    self.api.format_timestamp(timestamp), 
                                    patterns
                                )
                            
                            # 마지막 패턴 타임스탬프 업데이트
                            self.last_pattern_time[symbol][interval] = timestamp
            
            except Exception as e:
                print(f"{symbol} {interval} 업데이트 확인 중 오류:", e)
            
            # 각 간격에 맞는 적절한 슬립 시간 설정
            sleep_time = min(self.update_intervals[interval] / 2, 60 * 60)  # 최대 1시간
            time.sleep(sleep_time)

    def send_heartbeat(self):
        """1시간마다 작동 상태 알림 보내기"""
        while True:
            try:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message = f"🟢 <b>모니터링 상태</b>: 정상 작동 중\n⏰ <b>시간</b>: {current_time}\n"
                
                # 모니터링 중인 코인과 타임프레임 정보 추가
                coin_info = ", ".join([f"{symbol} ({', '.join(self.intervals)})" for symbol in self.symbols])
                message += f"📊 <b>모니터링 중</b>: {coin_info}"
                
                if self.telegram:
                    self.telegram.send_message(message)
                    print(f"{Fore.GREEN}하트비트 알림 전송 완료 - {current_time}{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"하트비트 알림 전송 오류: {e}")
            
            # 1시간 대기
            time.sleep(60 * 60)

    def start_periodic_detection(self):
        """주기적으로 패턴 감지 실행 (간격에 맞게)"""
        print(f'{Fore.CYAN}주기적인 패턴 감지 시작...{Style.RESET_ALL}')
        
        threads = []
        
        # 각 심볼과 간격에 대한 스레드 생성
        for symbol in self.symbols:
            for interval in self.intervals:
                thread = threading.Thread(
                    target=self.check_for_updates,
                    args=(symbol, interval),
                    daemon=True
                )
                threads.append(thread)
                thread.start()
        
        # 1시간마다 상태 알림 보내는 스레드 추가
        heartbeat_thread = threading.Thread(
            target=self.send_heartbeat,
            daemon=True
        )
        threads.append(heartbeat_thread)
        heartbeat_thread.start()
        
        # 메인 스레드에서는 무한 루프로 계속 실행
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n프로그램 종료.")

    def run(self):
        """앱 실행"""
        print(f'{Back.BLUE}{Fore.WHITE} 캔들 패턴 탐지기 시작... {Style.RESET_ALL}')
        
        # 초기 패턴 감지
        self.detect_all_patterns()
        
        # 주기적 패턴 감지 시작
        self.start_periodic_detection()


if __name__ == "__main__":
    # 텔레그램 설정
    # 이 값들을 자신의 봇 토큰과 채팅 ID로 변경하세요
    TELEGRAM_TOKEN = "7560465345:AAECpWzp7P2A944WW_1sNxPbjBWCi9vu2Os"
    TELEGRAM_CHAT_ID = "7016339719"
    
    # 환경 변수에서 텔레그램 토큰과 채팅 ID를 읽어올 수도 있습니다
    # TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
    # TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    # 앱 실행
    app = CandlePatternApp(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    app.run()