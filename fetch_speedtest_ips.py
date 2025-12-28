#!/usr/bin/env python3
"""
17CE 和 ITDog 测速节点抓取工具 - 命令行版本
适用于 GitHub Codespaces/Actions
使用方法: python3 fetch_speedtest_ips_cli.py
"""

import requests
import re
import json
import time
from datetime import datetime
import sys
import os
import ipaddress
from bs4 import BeautifulSoup
import argparse

class SpeedtestIPFetcherCLI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })
        self.timeout = 15
        
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def fetch_17ce(self, url):
        """抓取17CE节点"""
        self.log(f"正在抓取 17CE: {url}")
        results = set()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            self.log(f"状态码: {response.status_code}, 大小: {len(response.text)} 字节")
            
            content = response.text
            
            # 尝试多种提取方法
            patterns = [
                r'data-ip="([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"',
                r'"ip":"([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"',
                r"'ip': '([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})'",
                r'ip=([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for ip in matches:
                    if self.is_valid_ip(ip) and not self.is_private_ip(ip):
                        results.add(ip)
            
            # 查找可能的API
            api_patterns = [
                r'https?://[^"\']+/api/[^"\']+',
                r'https?://[^"\']+/data/[^"\']+',
                r'https?://[^"\']+/json/[^"\']+',
            ]
            
            for pattern in api_patterns:
                api_urls = re.findall(pattern, content)
                for api_url in api_urls[:2]:  # 只尝试前2个
                    try:
                        self.log(f"尝试API: {api_url}")
                        api_response = self.session.get(api_url, timeout=10)
                        if api_response.status_code == 200:
                            # 尝试解析JSON
                            try:
                                data = api_response.json()
                                self._extract_ips_from_data(data, results)
                            except:
                                # 从文本中提取
                                text_ips = re.findall(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', api_response.text)
                                for ip in text_ips:
                                    if self.is_valid_ip(ip) and not self.is_private_ip(ip):
                                        results.add(ip)
                    except:
                        continue
            
            # 从JavaScript中提取
            js_patterns = [
                r'var\s+nodes\s*=\s*(\[.*?\])',
                r'const\s+nodes\s*=\s*(\[.*?\])',
                r'let\s+nodes\s*=\s*(\[.*?\])',
            ]
            
            for pattern in js_patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        self._extract_ips_from_data(data, results)
                    except:
                        pass
            
        except requests.exceptions.RequestException as e:
            self.log(f"请求失败: {str(e)}")
        except Exception as e:
            self.log(f"解析失败: {str(e)}")
        
        self.log(f"从17CE找到 {len(results)} 个IP")
        return sorted(results)
    
    def fetch_itdog(self, url):
        """抓取ITDog节点"""
        self.log(f"正在抓取 ITDog: {url}")
        results = set()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            self.log(f"状态码: {response.status_code}, 大小: {len(response.text)} 字节")
            
            # 使用BeautifulSoup解析
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找 data-ip 属性
            for element in soup.find_all(attrs={"data-ip": True}):
                ip = element.get('data-ip')
                if self.is_valid_ip(ip) and not self.is_private_ip(ip):
                    results.add(ip)
            
            # 查找输入框中的IP
            for input_elem in soup.find_all('input'):
                value = input_elem.get('value', '')
                if self.is_valid_ip(value) and not self.is_private_ip(value):
                    results.add(value)
            
            # 从文本中提取
            text = soup.get_text()
            ip_matches = re.findall(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', text)
            for ip in ip_matches:
                if self.is_valid_ip(ip) and not self.is_private_ip(ip):
                    results.add(ip)
            
        except requests.exceptions.RequestException as e:
            self.log(f"请求失败: {str(e)}")
        except Exception as e:
            self.log(f"解析失败: {str(e)}")
        
        self.log(f"从ITDog找到 {len(results)} 个IP")
        return sorted(results)
    
    def _extract_ips_from_data(self, data, results):
        """从数据结构中递归提取IP"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    self._extract_ips_from_data(value, results)
                elif isinstance(value, str) and self.is_valid_ip(value):
                    if not self.is_private_ip(value):
                        results.add(value)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._extract_ips_from_data(item, results)
                elif isinstance(item, str) and self.is_valid_ip(item):
                    if not self.is_private_ip(item):
                        results.add(item)
    
    def is_valid_ip(self, ip):
        """验证IP地址格式"""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except:
            return False
    
    def is_private_ip(self, ip):
        """检查是否为私有IP"""
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
        except:
            return False
    
    def save_to_file(self, ips, filename, source):
        """保存到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# {source} 测速节点IP列表\n")
                f.write(f"# 抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 总共: {len(ips)} 个IP\n\n")
                for ip in ips:
                    f.write(f"{ip}\n")
            return True, filename
        except Exception as e:
            return False, str(e)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='抓取17CE和ITDog测速节点IP')
    parser.add_argument('--output-dir', '-o', default='./output', 
                       help='输出目录，默认为 ./output')
    parser.add_argument('--17ce-url', default='https://17ce.com/site/http',
                       help='17CE网址，默认为 https://17ce.com/site/http')
    parser.add_argument('--itdog-url', default='https://www.itdog.cn/http/',
                       help='ITDog网址，默认为 https://www.itdog.cn/http/')
    parser.add_argument('--no-save', action='store_true',
                       help='不保存文件，只显示结果')
    
    args = parser.parse_args()
    
    # 创建输出目录
    if not args.no_save and not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    print("=" * 60)
    print("    17CE & ITDog 测速节点抓取工具 (命令行版)")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"输出目录: {args.output_dir}")
    print(f"17CE URL: {args.17ce_url}")
    print(f"ITDog URL: {args.itdog_url}")
    print("-" * 60)
    
    fetcher = SpeedtestIPFetcherCLI()
    
    # 抓取17CE
    print("\n[1/2] 抓取 17CE 节点...")
    ips_17ce = fetcher.fetch_17ce(args.17ce_url)
    
    # 抓取ITDog
    print("\n[2/2] 抓取 ITDog 节点...")
    ips_itdog = fetcher.fetch_itdog(args.itdog_url)
    
    # 合并去重
    all_ips = sorted(set(ips_17ce + ips_itdog))
    
    print("\n" + "=" * 60)
    print("抓取完成!")
    print(f"17CE IP数量: {len(ips_17ce)}")
    print(f"ITDog IP数量: {len(ips_itdog)}")
    print(f"去重后总数: {len(all_ips)}")
    
    # 显示前20个IP
    if all_ips:
        print("\n前20个IP地址:")
        for i, ip in enumerate(all_ips[:20], 1):
            print(f"  {i:2d}. {ip}")
        if len(all_ips) > 20:
            print(f"  ... 还有 {len(all_ips) - 20} 个")
    else:
        print("\n警告: 没有找到任何IP地址!")
    
    # 保存文件
    if not args.no_save:
        print("\n保存结果...")
        
        # 保存17CE结果
        if ips_17ce:
            success, result = fetcher.save_to_file(
                ips_17ce, 
                os.path.join(args.output_dir, "17ce_ips.txt"),
                "17CE"
            )
            if success:
                print(f"✓ 17CE结果已保存: {result}")
            else:
                print(f"✗ 保存17CE失败: {result}")
        
        # 保存ITDog结果
        if ips_itdog:
            success, result = fetcher.save_to_file(
                ips_itdog,
                os.path.join(args.output_dir, "itdog_ips.txt"),
                "ITDog"
            )
            if success:
                print(f"✓ ITDog结果已保存: {result}")
            else:
                print(f"✗ 保存ITDog失败: {result}")
        
        # 保存合并结果
        if all_ips:
            success, result = fetcher.save_to_file(
                all_ips,
                os.path.join(args.output_dir, "speedtest_ips_combined.txt"),
                "17CE+ITDog合并"
            )
            if success:
                print(f"✓ 合并结果已保存: {result}")
            else:
                print(f"✗ 保存合并结果失败: {result}")
    
    print("\n" + "=" * 60)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
