import re
from bs4 import BeautifulSoup


def preprocess_html(content):
	'''
	对特殊符号'\'进行替换处理
	'''
	data = re.sub(r'<\\', '<', content)
	data = re.sub(r'\\"', '"', data)
	html_content = re.sub(r'\\/', '/', data)
	return html_content


def extract_FMView_html(content):
	'''
	提取FM.view数据格式中的html文本提取出来
	args: content: str
	'''
	html_content = ''
	blocks = re.findall(r'<script>FM.view\((.+)\)</script>', content)
	for block in blocks:
		dict_ = eval(block)
		if 'html' in dict_:
			data = dict_['html']
			html_content += preprocess_html(data)
	return html_content



def parse_search_page(content):
	'''
	从页面内容中提取出所有贴子的id
	'''
	posts_id = []
	soup = BeautifulSoup(content, 'lxml')
	for post_item in soup.find_all(attrs={'action-type':'feed_list_item'}):
		post_data = {}
		# rid
		rid_item = post_item.find(class_=['WB_from', 'S_txt2'])
		posts_id.append(re.search(r'/.+/(.+)\?.+', rid_item.find('a')['href']).group(1))

	return posts_id
	


def parse_post_details(content):
	'''
	提取帖子的post_id（用于爬rid）、mid（用于爬取评论）、发布时间、内容、其他链接
	'''
	# 从html正文中爬取其他信息
	soup = BeautifulSoup(content, 'lxml')
	post_data = {}
	# mid
	# print(content)
	post_data['mid'] = soup.find(attrs={'action-data':'cur_visible=0'})['mid']
	# 发布时间
	post_data['datetime'] = soup.find(attrs={'node-type':'feed_list_item_date'}).text
	# 文本内容
	post_data['content'] = soup.find(attrs={'node-type':'feed_list_content'}).text
	# 相关链接（视频、文章等）
	if soup.find(attrs={'action-type':'feed_list_url'}):
		post_data['extra_link'] = soup.find(attrs={'action-type':'feed_list_url'})['href']
	else:
		post_data['extra_link'] = None
	# 转赞评
	feed_data = []
	feed_item = soup.find(class_=['WB_handle'])
	for item in feed_item.find_all('a'):
		text = item.text
		if '收藏' in text: continue
		feed_data.append(int(re.search(r'[^\d]+(\d+)[^\d]*', text).group(1)))
	post_data.update(dict(zip(['repost', 'comment', 'like'], feed_data)))

	return post_data



# 解析评论数据
def parse_comments_page(content):
	'''
	提取出评论信息
	'''
	comments = []
	soup = BeautifulSoup(content, 'lxml')
	for comment_item in soup.find_all(attrs={'node-type':'replywrap'}):
		comment_data = {}
		# 评论内容
		if comment_item.find(class_=['WB_text']):
			text = comment_item.find('div', class_=['WB_text']).text
			comment_data['content'] = re.search(r'.*：(.+)', text).group(1)
		else:
			print(comment_item)
			break
		# 评论时间
		comment_data['datetime'] = comment_item.find(class_=['WB_from']).text
		# 点赞
		like_text = comment_item.find(class_=['WB_handle', 'W_fr']).find(attrs={'node-type': 'like_status'}).text
		if '赞' in like_text:
			comment_data['likecount'] = 0
		else:
			comment_data['likecount'] = re.search(r'[^\d]*(\d+)', like_text).group(1)
		comments.append(comment_data)

	return comments




