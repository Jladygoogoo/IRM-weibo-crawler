import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, ALL_COMPLETED, wait


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


def start_threads(func, args_dicts):
    with ThreadPoolExecutor(max_workers=5) as executor:
      tasks = []
      for args_dict in args_dicts:
        tasks.append(executor.submit(func, **args_dict)) # 将新的任务添加进线程池
      wait(tasks, return_when=ALL_COMPLETED) # 阻塞等待所有任务


def start_hetero_loop(tasks):
    # 创建不同性质任务下的协程
    # tasks: [{'func':func1, 'args':[...]}, ...]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [loop.create_task(task['func'](*task['args'])) for task in tasks]
    loop.run_until_complete(tasks)
    loop.close()


def map_likecount_to_int():
    '''
    1. 之前因为疏忽导致评论数据文件中 likecount 的非零值使用了字符串存储，本函数将其重写为整型
    2. 不知道为什么扒下来的评论有重复，需要进行整理
    '''
    root_dir = 'data'
    for root, dirs, files in os.walk(root_dir):
        for dir_ in dirs:
            base_dir = '{}/{}/comments'.format(root_dir, dir_)
            for file in os.listdir(base_dir):
                if 'DS' in file: continue
                with open(os.path.join(base_dir, file)) as f:
                    content = json.load(f)
                    new_content = []
                    for item in content:
                        item['likecount'] = int(item['likecount'])
                        new_content.append(item)
                    write_dir = 'data/{}/comments'.format(dir_)
                    if not os.path.exists(write_dir):
                        os.makedirs(write_dir)
                    with open(os.path.join(write_dir, file), 'w') as f:
                        json.dump(new_content, f, ensure_ascii=False, indent=2)
        break

if __name__ == '__main__':
    map_likecount_to_int()



