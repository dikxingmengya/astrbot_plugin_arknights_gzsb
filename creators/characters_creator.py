from bs4 import BeautifulSoup
import json

def create():
    # 读取HTML文件
    with open('../resource/tags.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    tbody = soup.find('tbody', {'data-v-3ee5781a': ''})

    characters_data = {"characters": {}}

    if tbody:
        # 找到所有的头像容器
        char_divs = tbody.find_all('div', class_='avatar-container')

        for char_div in char_divs:
            name_elem = char_div.find('a')
            img_elem = char_div.find('img', class_='avatar')
            rarity_elem = char_div.find('div', class_='rarity').find('img') if char_div.find('div',
                                                                                             class_='rarity') else None
            profession_elem = char_div.find('div', class_='profession').find('img') if char_div.find('div',
                                                                                                     class_='profession') else None

            if name_elem and img_elem:
                # 提取名字
                name_path = name_elem['href'].split('/')[-1]
                name = name_path.split('(')[0].split('#')[0]

                # 提取链接
                avatar_url = img_elem['src']
                rarity_url = rarity_elem['src'] if rarity_elem else ''
                profession_url = profession_elem['src'] if profession_elem else ''
                level = int(rarity_url[-5]) + 1

                # 构建数据结构
                characters_data["characters"][name] = {
                    "star": level,
                    "avatar": avatar_url,
                    "rarity": rarity_url,
                    "profession": profession_url
                }

    # 写入JSON文件
    with open('../characters.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(characters_data, ensure_ascii=False, indent=2))

    print(" characters.json 生成完成")

if __name__ == "__main__":
    create()