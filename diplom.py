from datetime import datetime

import requests
import argparse
import sys
import json
import time


TOKEN = '958eb5d439726565e9333aa30e50e0f937ee432e927f0dbd541c541887d919a7c56f95c04217915c32008'


class Error(Exception):
    pass


class ApiVK:
    params = {
        'v': '5.61',
        'access_token': TOKEN
    }

    api_vk_url = 'https://api.vk.com/method/'
    vk_url = 'https://vk.com/'

    @staticmethod
    def execute(user_id, method, method_params):
        resp = ApiVK.execute_with_timeout(method, method_params)

        if 'error' in resp.json():
            ApiVK.check_errors(user_id, resp.json()['error']['error_code'], resp.json()['error']['error_msg'])

        return resp

    @staticmethod
    def execute_with_timeout(method, method_params):
        while True:
            resp = requests.get(''.join((ApiVK.api_vk_url, method)), params=method_params)

            if 'error' in resp.json() and resp.json()['error']['error_code'] == 6:
                time.sleep(0.5)
            else:
                return resp

    @staticmethod
    def check_errors(user_id, error_code, description):
        if error_code == 18:
            raise Error(f'Пользователь {user_id} удален или заблокирован.')
        elif error_code == 7:
            raise Error(f'Пользователь {user_id} закрыл доступ к списку групп.')
        elif error_code == 15:
            raise Error(f'Страница пользователя {user_id} скрыта.')
        else:
            raise Error(description)


class VKGroup(ApiVK):
    @staticmethod
    def get_info(group_id):
        params = ApiVK.params
        params['group_id'] = group_id
        params['fields'] = ['name', 'members_count']

        resp = ApiVK.execute_with_timeout('groups.getById', params)

        try:
            group_info = dict()
            group_info['name'] = resp.json()['response'][0]['name']
            group_info['gid'] = resp.json()['response'][0]['id']
            group_info['members_count'] = resp.json()['response'][0]['members_count']
            return group_info
        except Exception:
            raise Error(f'Не удалось получить необходимую информацию о сообществе {group_id}')


class VKUser(ApiVK):
    def __init__(self, user_id):
        if isinstance(user_id, int) or isinstance(user_id, str) and user_id.isdigit():
            self.id = user_id
        else:
            self.get_id(user_id)

    def __str__(self):
        return f'{ApiVK.vk_url}id{int(self.id)}'

    def __hash__(self):
        return self.id.__hash__()

    def __eq__(self, other):
        return self.id == other.id

    def get_id(self, name):
        params = ApiVK.params
        params['user_ids'] = name

        resp = ApiVK.execute(name, 'users.get', params)

        self.id = resp.json()['response'][0]['id']

    def get_friends(self):
        params = ApiVK.params
        params['user_id'] = self.id
        resp = ApiVK.execute(self.id, 'friends.get', ApiVK.params)

        friends_id = resp.json()['response']['items']
        friends = list()
        for id in friends_id:
            friends.append(VKUser(id))

        return friends

    def get_groups(self):
        params = ApiVK.params
        params['user_id'] = self.id

        resp = ApiVK.execute(self.id, 'groups.get', params)

        return set(resp.json()['response']['items'])


def create_parser():
    parser = argparse.ArgumentParser(description='Получение списка групп, '
                                     'в которых состоит пользователь, но не состоит никто из его друзей.')
    parser.add_argument('user_id',
                        metavar='user_id',
                        help='имя пользователя или его ID')
    return parser


def main(arguments):
    start = datetime.now()

    main_user = VKUser(arguments.user_id)
    print(f'Скрипт выполняется для пользователя {main_user}.')

    print('Запрос информации о друзьях пользователя...', end='')
    all_friends = main_user.get_friends()
    friends_count = len(all_friends)
    print(f'\rВсего друзей: {len(all_friends)}.{" " * 30}')

    print('Запрос информации о группах пользователя...', end='')
    main_user_groups = main_user.get_groups()
    groups_count = len(main_user_groups)
    print(f'\rПользователь состоит в {groups_count} группе(-ах).')

    print('Запрос информации о группах каждого из друзей пользователя...')
    for ctr, friend in enumerate(all_friends):
        print(f'Проверяется пользователь {friend.id} ({ctr + 1}/{friends_count})... ', end='')
        try:
            friend_groups = friend.get_groups()
            main_user_groups = set.difference(main_user_groups, friend_groups)
            print('\r', end='')
        except Error as e:
            print(f'\r\t{e}')
            continue

    print('Этап проверки групп друзей завершен. Начат сбор сведений о самих группах...')
    groups_info = list()
    uniq_groups_count = len(main_user_groups)
    for ctr, group in enumerate(main_user_groups):
        print(f'\rПолучение информации о группе {group} ({ctr + 1}/{uniq_groups_count})...', end='')
        groups_info.append(VKGroup.get_info(group))

    print('\rВыходные данные сформированы. Производится запись в файл...')
    with open('groups.json', 'w', encoding='utf-16') as fp:
        json.dump(groups_info, fp, indent='\t', ensure_ascii=False)

    print(f'В {uniq_groups_count} из {groups_count} групп, в которых состоит пользователь {main_user.id} '
          f'не состоит никто из его друзей.\n'
          f'Сведения о выделенных группах сохранены в файл <groups.json>.\n'
          f'Время работы: {datetime.now() - start}.')


if __name__ == '__main__':
    arguments = create_parser()

    if len(sys.argv) != 2:
        arguments.print_help()
    else:
        main(arguments.parse_args())
