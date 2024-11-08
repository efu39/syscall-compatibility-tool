import re
import urllib.request

# sorted_by possible value:
#  'by_inst'
#  'by_vote'
def get_package_popularity(field):
    url = "https://popcon.debian.org/"
    popularity = dict()
    data = urllib.request.urlopen(url + 'by_' + field)
    for line in data:
        linestr = line.decode('utf-8')
        # Ignore comments
        if linestr.startswith('#'):
            continue

        if linestr.startswith('-'):
            continue

        results = linestr.strip().split(None,7)
        if len(results) < 4:
            continue
        package_name = results[1]

        if re.search(r'[^A-Za-z0-_\+\-\.]', package_name):
            continue

        if package_name not in popularity:
            values = dict()
            values['rank'] = int(results[0])
            values['inst'] = int(results[2])
            values['vote'] = int(results[3])
            values['maintainer'] = results[7]
            popularity[package_name] = values
        else:
            print('package_name duplicated?')
            exit()

    packages = []
    for (package_name, values) in popularity.items():
        values['package_name'] = package_name
        packages.append(values)

    return packages

if __name__ == "__main__":
    field = 'inst'
    for pkg in get_package_popularity(field):
        print(f'{pkg['rank']}: {pkg['package_name']} ({pkg[field]})')
