#coding:utf-8

import requests
import socket
import random
import json
import sys

CHROME = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.115 Safari/537.36'
HEADER = {'Connection': 'keep-alive', 'User-Agent': CHROME}
AK = 'owaggfQTFcE3tmuCG5g1LnCLZSYImGTU'

# # 全上海的范围
# sh_lower_left_lat = 30.891077
# sh_lower_left_lng = 121.12438
# # all sh
# sh_upper_right_lat = 31.421996
# sh_upper_right_lng = 121.87253


#===============
# small block
# upper_right_lat = 30.941996
# upper_right_lng = 121.17253

# big block
# upper_right_lat = 31.021077
# upper_right_lng = 121.27438

overlap_ratio = 7.0/8.0

# 定义了一个点
class Location:
	def __init__(self, lat, lng):
		self.lat = lat
		self.lng = lng

sh_lower_left = Location(lat = 30.891077, lng = 121.12438)
sh_upper_right = Location(lat = 31.421996, lng = 121.87253)

# 定义了地图上的一个矩形块
class Block:
	def __init__(self, left_lower, right_upper, width, height):
		self.left_lower = left_lower
		self.right_upper = right_upper
		self.width = width
		self.height = height

class BaiduPOICrawler:

	def _get_block_poi_result(self, block, poi_name, page):
		# ak = AK[random.randint(0, len(AK)-1)]
		# lat,lng(左下角坐标),lat,lng(右上角坐标)
		global AK
		url = 'http://api.map.baidu.com/place/v2/search?query={}&page_size=20&page_num={}\
		&scope=2&bounds={},{},{},{}&output=json&ak={}'.format(poi_name, page,
			block.left_lower.lat, block.left_lower.lng, block.right_upper.lat, block.right_upper.lng, AK)
		json_str = self.query_json(url)
		json_dict = json.loads(json_str)
		return json_dict

	def query_json(self, url):
		while True:
			try:
				r = requests.get(url, headers= HEADER).text
			except (socket.timeout, requests.exceptions.Timeout):  # socket.timeout
				print "timeout", url
			except requests.exceptions.ConnectionError:
				print "connection error", url
			else:
				try:
					json.loads(r)
				except ValueError:
					print "no json return, retry."
				except:
					print "unknown error, retry."
				else:
					break
		return r

	def load_poi_type(self, filename):
		self.poi_types = {}
		# each line: 美食#中餐厅,外国餐厅,小吃快餐店,蛋糕甜品店,咖啡厅茶座,酒吧
		# 一级行业分类#二级行业分类[用,分隔]
		with open(filename, 'r') as fin:
			for line in fin:
				data = line.strip().decode('utf-8').split('#')
				first_calss_cat = data[0]
				second_class_cat_list = data[1].split(',')
				self.poi_types[first_calss_cat] = second_class_cat_list

	def get_block_scope(self, origin, width, height, row_idx, col_idx):
		# 返回值是一个Block对象！！！
		# 例如0,0也就是整个上海市最左下角的第一个格子的左下角和右上角坐标
		# origin: Location 当前区域内的原点
		# width: 当前区域内预计的格子宽度
		# height: 当前区域内预计的格子高度
		# row_idx, col_idx: 当前格子在当前区域的位置
		global overlap_ratio
		row_interval = overlap_ratio*width
		col_interval = overlap_ratio*height
		left_lower = Location(lat = origin.lat + row_idx*row_interval, lng = origin.lng + col_idx*col_interval)
		right_upper = Location(lat = left_lower.lat + height, lng = left_lower.lng + width)
		return Block(left_lower, right_upper, width, height)

	def block_is_proper(self, block, poi_name):
		# 查看当前分块的width和height, 对于某个poi, 请求下来的内容是不是小于400，小于400就是全的，=400就要继续缩小格子
		# block: Block
		result = self._get_block_poi_result(block, poi_name, 0)
		print(result)
		# 这里可能出现网络返回值问题
		if (result['status'] == 0) and (result['total'] != 400):
			return (True, result) # result['results']是一个list,每一个元素是一个dict
		else:
			return (False, [])

	def write_res(self, a_list, filename):
		# a_list是一页请求回来的，有20个数据
		with open(filename, 'a+') as fout:
			fout.write(json.dumps(a_list, ensure_ascii=False, separators=(',', ':')).encode('utf-8')+'\n')

	def block_is_good_to_write(self, res, block, poi_name):
		fname = 'data_20160429/{}.txt'.format(poi_name)
		self.write_res(a_list = res['results'], filename = fname)
		print("{}: success, total:{}条poi, page 0".format(poi_name, res['total']))
		page_sum = res['total']/20
		if page_sum == 0:
			return
		last_page = page_sum if (res['total']%20 == 0) else (page_sum+1)
		for i in range(1, last_page):
			res_dict = self._get_block_poi_result(block, poi_name, i)
			if (res_dict['status'] == 0) and (res_dict['total'] != 0):
				self.write_res(res_dict['results'], fname)
				print("{}: success, total:{}条poi, page {}".format(poi_name, res_dict['total'], i))
			elif res_dict['status'] != 0:
				self.write_error_log(block, poi_name, i)


	def split_block_to_half(self, block, poi_name):
		# 将block划分成更小的block，对半分
		print("poi:{}, lat:{}, lng:{}, current width:{}, current height:{}, too big and cut half".format(poi_name, block.left_lower.lat, block.left_lower.lng ,block.width, block.height))
		for i in range(2):
			for j in range(2):
				# 生成一个subblock：Block类型
				current_block_width = block.width
				current_block_height = block.height
				sub_block = self.get_block_scope(block.left_lower, 0.5*current_block_width, 0.5*current_block_height, i, j)
				self.get_block_all_poi(sub_block, poi_name)

	def exit_prog(self):
		# 换ak
		print("日配额已经用完")
		sys.exit(0)

	def write_error_log(self, block, poi_name, page):
		import datetime, os
		logfile = datetime.datetime.now().strftime("%Y%m%d") + '.log'
		if os.path.isfile(logfile):
			f = open(logfile, 'a+')
		else:
			f = open(logfile, 'w')
		f.write('left_lower_lat:{}, left_lower_lng:{}, right_upper_lat:{}, \
			right_upper_lng:{}, poiType:{}, page:{}, fail\n'.format(block.left_lower.lat, 
			block.left_lower.lng, block.right_upper.lat, block.right_upper.lng, poi_name, page))
		f.close()


	def get_block_all_poi(self, block, poi_name):
		# 完整的请求一个block中某一poi的全部信息
		# status, res = self.block_is_proper(block, poi_name)

		# 先请求第一页,根据第一页的结果指定相应的对策
		result = self._get_block_poi_result(block, poi_name, 0)
		if (result['status'] == 0) and (result['message'] == u'ok') and (result['total'] == 0):
			return
		elif (result['status'] == 0) and (result['total'] != 0) and (result['total'] < 400):
			self.block_is_good_to_write(result, block, poi_name)
		elif (result['status'] == 0) and (result['total'] == 400):
			self.split_block_to_half(block, poi_name)
		elif result['status'] == 302:
			self.exit_prog()
		else: # 其他意外写入log文件
			self.write_error_log(block, poi_name, 0)

	def all_sub_pois(self):
		l = []
		for i in self.poi_types.values():
			l.extend(i)
		return l

	def get_pois(self):
		l = [u'中餐厅',u'外国餐厅',u'小吃快餐店',u'蛋糕甜品店',u'咖啡厅',u'茶座',u'酒吧']
		return l

	def start(self):
		width = 0.15
		height = 0.13
		lat_N = 5
		lng_N = 6
		global sh_lower_left
		for i in range(lng_N):
			for j in range(lat_N):
				block = self.get_block_scope(sh_lower_left, width, height, i, j)
				for poi in self.get_pois():
					self.get_block_all_poi(block, poi.encode('utf-8'))


def main():
	crawler = BaiduPOICrawler()
	crawler.load_poi_type(filename = 'poi_type.txt')
	crawler.start()

if __name__ == '__main__':
	main()
