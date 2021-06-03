import os
import json
import asyncio

def get_cookies(cookies_file):
	# 将cookies转换为字典
	content = open(cookies_file).read()
	cookies_dict = {cookie.split('=')[0]:cookie.split('=')[1] for cookie in content.split('; ')}
	return cookies_dict


def write_json_data(data, filepath=None, fileobj=None):	
	# 将数据写到本地
	if filepath:
		write_dir = os.path.dirname(filepath)
		if not os.path.exists(write_dir):
			os.makedirs(write_dir)
		with open(filepath, 'w') as f:
			json.dump(data, f, indent=2, ensure_ascii=False)
	else:
		json.dump(data, fileobj, indent=2, ensure_ascii=False)


def start_homo_loop(func, args_dicts):
	# 创建同性质任务下的协程
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	tasks = [loop.create_task(func(**args_dict)) for args_dict in args_dicts]
	loop.run_until_complete(asyncio.wait(tasks))
	loop.close()


def start_hetero_loop(tasks):
	# 创建不同性质任务下的协程
	# tasks: [{'func':func1, 'args':[...]}, ...]
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	tasks = [loop.create_task(task['func'](*task['args'])) for task in tasks]
	loop.run_until_complete(tasks)
	loop.close()
