from __future__ import absolute_import, division, print_function, unicode_literals

import math
import re
from datetime import datetime
from struct import pack

from helpers import coord2int, int2coord

# Don't change this setup or timezonefinder wont work!
# different setups of shortcuts are not supported, because then addresses in the .bin
# would need to be calculated depending on how many shortcuts are being used.
# number of shortcuts per longitude
NR_SHORTCUTS_PER_LNG = 1
# shortcuts per latitude
NR_SHORTCUTS_PER_LAT = 2

all_tz_names = []
ids = []
boundaries = []
all_coords = []
all_lengths = []


# HELPERS:

def update_zone_names(path='timezone_names.py'):
    '''
    TODO
    :return:
    '''
    print('updating the zone names now')
    unique_zones = []
    for zone_name in all_tz_names:

        if zone_name not in unique_zones:
            unique_zones.append(zone_name)

    unique_zones.sort()

    for zone_name in all_tz_names:
        # the ids of the polygons have to be set correctly
        ids.append(unique_zones.index(zone_name))

    # write all unique zones into the file at path with the syntax of a python array
    file = open(path, 'w')
    file.write(
        'from __future__ import absolute_import, division, print_function, unicode_literals\n\ntimezone_names = [\n')
    for zone_name in unique_zones:
        file.write('    "' + zone_name + '"' + ',\n')

    file.write(']\n')
    print('Done\n')


def inside_polygon(x, y, x_coords, y_coords):
    def is_left_of(x, y, x1, x2, y1, y2):
        return (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1)

    n = len(y_coords) - 1

    wn = 0
    for i in range(n):
        iplus = i + 1
        if y_coords[i] <= y:
            # print('Y1<=y')
            if y_coords[iplus] > y:
                # print('Y2>y')
                if is_left_of(x, y, x_coords[i], x_coords[iplus], y_coords[i], y_coords[iplus]) > 0:
                    wn += 1
                    # print('wn is:')
                    # print(wn)

        else:
            # print('Y1>y')
            if y_coords[iplus] <= y:
                # print('Y2<=y')
                if is_left_of(x, y, x_coords[i], x_coords[iplus], y_coords[i], y_coords[iplus]) < 0:
                    wn -= 1
                    # print('wn is:')
                    # print(wn)

    return wn is not 0


def parse_polygons_from_json(path='tz_world.json'):
    f = open(path, 'r')
    print('Parsing data from .json')
    n = 0
    for row in f:

        if n % 1000 == 0:
            print('line', n)

        n += 1
        # print(row)
        tz_name_match = re.search(r'\"TZID\":\s\"(?P<name>.*)\"\s\}', row)
        # tz_name = re.search(r'(TZID)', row)
        # print(tz_name)
        if tz_name_match is not None:

            tz_name = tz_name_match.group('name').replace('\\', '')
            all_tz_names.append(tz_name)
            # print(tz_name)

            coordinates = re.findall('[-]?\d+\.?\d+', row)
            # print(coordinates)

            # nr_floats = len(coordinates)
            x_coords = []
            y_coords = []
            i = 0
            for coord in coordinates:
                if i % 2 == 0:
                    x_coords.append(float(coord))
                else:
                    y_coords.append(float(coord))
                i += 1

            if i % 2 != 0:
                raise ValueError(i, 'Floats in line', n, ' found. Should be even (pairs or (x,y) )')

            all_coords.append((x_coords, y_coords))
            all_lengths.append(len(x_coords))
            # print(x_coords)
            # print(y_coords)
            xmax = -180.0
            xmin = 180.0
            ymax = -90.0
            ymin = 90.0

            for x in x_coords:

                if x > xmax:
                    xmax = x
                if x < xmin:
                    xmin = x

            for y in y_coords:
                if y > ymax:
                    ymax = y
                if y < ymin:
                    ymin = y

            boundaries.append((xmax, xmin, ymax, ymin))

    print('Done\n')


def _ids():
    for id in ids:
        yield id


def _boundaries():
    for b in boundaries:
        yield b


def _coordinates():
    for c in all_coords:
        yield c


def ints_of(line=0):
    x_coords, y_coords = all_coords[line]
    return [coord2int(x) for x in x_coords], [coord2int(x) for x in y_coords]


def _length_of_rows():
    for length in all_lengths:
        yield length


def compile_into_binary(path='tz_binary.bin'):
    nr_of_floats = 0
    nr_of_lines = 0
    zone_ids = []
    shortcuts = {}

    def x_shortcut(lng):
        # if lng < -180 or lng >= 180:
        # print(lng)
        # raise ValueError('longitude out of bounds')
        return math.floor((lng + 180) * NR_SHORTCUTS_PER_LNG)

    def y_shortcut(lat):
        # if lat < -90 or lat >= 90:
        # print(lat)
        # raise ValueError('this latitude is out of bounds')
        return math.floor((90 - lat) * NR_SHORTCUTS_PER_LAT)

    def big_zone(xmax, xmin, ymax, ymin):
        # returns True if a zone with those boundaries could have more than 4 shortcuts
        return xmax - xmin > 2 / NR_SHORTCUTS_PER_LNG and ymax - ymin > 2 / NR_SHORTCUTS_PER_LAT

    def included_shortcut_row_nrs(max_lat, min_lat):
        return list(range(y_shortcut(max_lat), y_shortcut(min_lat) + 1))

    def included_shortcut_column_nrs(max_lng, min_lng):
        return list(range(x_shortcut(min_lng), x_shortcut(max_lng) + 1))

    def longitudes_to_check(max_lng, min_lng):
        output_list = []
        step = 1 / NR_SHORTCUTS_PER_LNG
        current = math.ceil(min_lng * NR_SHORTCUTS_PER_LNG) / NR_SHORTCUTS_PER_LNG
        end = math.floor(max_lng * NR_SHORTCUTS_PER_LNG) / NR_SHORTCUTS_PER_LNG
        while current < end:
            output_list.append(current)
            current += step

        output_list.append(end)
        return output_list

    def latitudes_to_check(max_lat, min_lat):
        output_list = []
        step = 1 / NR_SHORTCUTS_PER_LAT
        current = math.ceil(min_lat * NR_SHORTCUTS_PER_LAT) / NR_SHORTCUTS_PER_LAT
        end = math.floor(max_lat * NR_SHORTCUTS_PER_LAT) / NR_SHORTCUTS_PER_LAT
        while current < end:
            output_list.append(current)
            current += step

        output_list.append(end)
        return output_list

    def compute_x_intersection(y, x1, x2, y1, y2):
        """returns the x intersection from a horizontal line in y with the line from x1,y1 to x1,y2
        """
        delta_y = y2 - y1
        if delta_y == 0:
            return x1
        return ((y - y1) * (x2 - x1) / delta_y) + x1

    def compute_y_intersection(x, x1, x2, y1, y2):
        """returns the y intersection from a vertical line in x with the line from x1,y1 to x1,y2
        """
        delta_x = x2 - x1
        if delta_x == 0:
            return x1
        return ((x - x1) * (y2 - y1) / delta_x) + y1

    def x_intersections(y, x_coords, y_coords):

        # print(x_coords)
        # print(y)
        # print(y_coords)

        intersects = []
        for i in range(len(y_coords) - 1):
            iplus1 = i + 1
            if y_coords[i] <= y:
                # print('Y1<=y')
                if y_coords[iplus1] > y:
                    # this was a crossing. compute the intersect
                    # print('Y2>y')
                    intersects.append(
                        compute_x_intersection(y, x_coords[i], x_coords[iplus1], y_coords[i], y_coords[iplus1]))
            else:
                # print('Y1>y')
                if y_coords[iplus1] <= y:
                    # this was a crossing. compute the intersect
                    # print('Y2<=y')
                    intersects.append(compute_x_intersection(y, x_coords[i], x_coords[iplus1], y_coords[i],
                                                             y_coords[iplus1]))
        return intersects

    def y_intersections(x, x_coords, y_coords):

        intersects = []
        for i in range(len(y_coords) - 1):
            iplus1 = i + 1
            if x_coords[i] <= x:
                if x_coords[iplus1] > x:
                    # this was a crossing. compute the intersect
                    intersects.append(
                        compute_y_intersection(x, x_coords[i], x_coords[iplus1], y_coords[i], y_coords[iplus1]))
            else:
                if x_coords[iplus1] <= x:
                    # this was a crossing. compute the intersect
                    intersects.append(compute_y_intersection(x, x_coords[i], x_coords[iplus1], y_coords[i],
                                                             y_coords[iplus1]))
        return intersects

    def compute_exact_shortcuts(xmax, xmin, ymax, ymin, line):
        shortcuts_for_line = set()

        # x_longs = binary_reader.x_coords_of(line)
        longs = ints_of(line)
        x_longs = longs[0]
        y_longs = longs[1]

        # y_longs = binary_reader.y_coords_of(line)
        y_longs.append(y_longs[0])
        x_longs.append(x_longs[0])

        step = 1 / NR_SHORTCUTS_PER_LAT
        # print('checking the latitudes')
        for lat in latitudes_to_check(ymax, ymin):
            # print(lat)
            # print(coordinate_to_longlong(lat))
            # print(y_longs)
            # print(x_intersections(coordinate_to_longlong(lat), x_longs, y_longs))
            # raise ValueError
            intersects = sorted([int2coord(x) for x in
                                 x_intersections(coord2int(lat), x_longs, y_longs)])
            # print(intersects)

            nr_of_intersects = len(intersects)
            if nr_of_intersects % 2 != 0:
                raise ValueError('an uneven number of intersections has been accounted')

            for i in range(0, nr_of_intersects, 2):
                possible_longitudes = []
                # collect all the zones between two intersections [in,out,in,out,...]
                iplus = i + 1
                intersection_in = intersects[i]
                intersection_out = intersects[iplus]
                if intersection_in == intersection_out:
                    # the polygon has a point exactly on the border of a shortcut zone here!
                    # only select the top shortcut if it is actually inside the polygon (point a little up is inside)
                    if inside_polygon(coord2int(intersection_in), coord2int(lat) + 1, x_longs,
                                      y_longs):
                        shortcuts_for_line.add((x_shortcut(intersection_in), y_shortcut(lat) - 1))
                    # the bottom shortcut is always selected
                    shortcuts_for_line.add((x_shortcut(intersection_in), y_shortcut(lat)))

                else:
                    # add all the shortcuts for the whole found area of intersection
                    possible_y_shortcut = y_shortcut(lat)

                    # both shortcuts should only be selected when the polygon doesnt stays on the border
                    middle = intersection_in + (intersection_out - intersection_in) / 2
                    if inside_polygon(coord2int(middle), coord2int(lat) + 1, x_longs,
                                      y_longs):
                        while intersection_in < intersection_out:
                            possible_longitudes.append(intersection_in)
                            intersection_in += step

                        possible_longitudes.append(intersection_out)

                        # the shortcut above and below of the intersection should be selected!
                        possible_y_shortcut_min1 = possible_y_shortcut - 1
                        for possible_x_coord in possible_longitudes:
                            shortcuts_for_line.add((x_shortcut(possible_x_coord), possible_y_shortcut))
                            shortcuts_for_line.add((x_shortcut(possible_x_coord), possible_y_shortcut_min1))
                    else:
                        # polygon does not cross the border!
                        while intersection_in < intersection_out:
                            possible_longitudes.append(intersection_in)
                            intersection_in += step

                        possible_longitudes.append(intersection_out)

                        # only the shortcut above of the intersection should be selected!
                        for possible_x_coord in possible_longitudes:
                            shortcuts_for_line.add((x_shortcut(possible_x_coord), possible_y_shortcut))

        # print('now all the longitudes to check')
        # same procedure horizontally
        step = 1 / NR_SHORTCUTS_PER_LAT
        for lng in longitudes_to_check(xmax, xmin):
            # print(lng)
            # print(coordinate_to_longlong(lng))
            # print(x_longs)
            # print(x_intersections(coordinate_to_longlong(lng), x_longs, y_longs))
            intersects = sorted([int2coord(y) for y in
                                 y_intersections(coord2int(lng), x_longs, y_longs)])
            # print(intersects)

            nr_of_intersects = len(intersects)
            if nr_of_intersects % 2 != 0:
                raise ValueError('an uneven number of intersections has been accounted')

            possible_latitudes = []
            for i in range(0, nr_of_intersects, 2):
                # collect all the zones between two intersections [in,out,in,out,...]
                iplus = i + 1
                intersection_in = intersects[i]
                intersection_out = intersects[iplus]
                if intersection_in == intersection_out:
                    # the polygon has a point exactly on the border of a shortcut here!
                    # only select the left shortcut if it is actually inside the polygon (point a little left is inside)
                    if inside_polygon(coord2int(lng) - 1, coord2int(intersection_in), x_longs,
                                      y_longs):
                        shortcuts_for_line.add((x_shortcut(lng) - 1, y_shortcut(intersection_in)))
                    # the right shortcut is always selected
                    shortcuts_for_line.add((x_shortcut(lng), y_shortcut(intersection_in)))

                else:
                    # add all the shortcuts for the whole found area of intersection
                    possible_x_shortcut = x_shortcut(lng)

                    # both shortcuts should only be selected when the polygon doesnt stays on the border
                    middle = intersection_in + (intersection_out - intersection_in) / 2
                    if inside_polygon(coord2int(lng) - 1, coord2int(middle), x_longs,
                                      y_longs):
                        while intersection_in < intersection_out:
                            possible_latitudes.append(intersection_in)
                            intersection_in += step

                        possible_latitudes.append(intersection_out)

                        # both shortcuts right and left of the intersection should be selected!
                        possible_x_shortcut_min1 = possible_x_shortcut - 1
                        for possible_latitude in possible_latitudes:
                            shortcuts_for_line.add((possible_x_shortcut, y_shortcut(possible_latitude)))
                            shortcuts_for_line.add((possible_x_shortcut_min1, y_shortcut(possible_latitude)))

                    else:
                        while intersection_in < intersection_out:
                            possible_latitudes.append(intersection_in)
                            intersection_in += step
                        # only the shortcut right of the intersection should be selected!
                        possible_latitudes.append(intersection_out)

                        for possible_latitude in possible_latitudes:
                            shortcuts_for_line.add((possible_x_shortcut, y_shortcut(possible_latitude)))

        return shortcuts_for_line

    def construct_shortcuts():
        print('building shortucts...')
        print('currently in line:')
        line = 0
        for xmax, xmin, ymax, ymin in _boundaries():
            # xmax, xmin, ymax, ymin = boundaries_of(line=line)
            if line % 1000 == 0:
                print('line ' + str(line))
                # print([xmax, xmin, ymax, ymin])

            column_nrs = included_shortcut_column_nrs(xmax, xmin)
            row_nrs = included_shortcut_row_nrs(ymax, ymin)

            if big_zone(xmax, xmin, ymax, ymin):

                '''
                print('line ' + str(line))
                print('This is a big zone! computing exact shortcuts')
                print('Nr of entries before')
                print(len(column_nrs) * len(row_nrs))

                print('columns and rows before optimisation:')

                print(column_nrs)
                print(row_nrs)
                '''

                # This is a big zone! compute exact shortcuts with the whole polygon points
                shortcuts_for_line = compute_exact_shortcuts(xmax, xmin, ymax, ymin, line)
                # n += len(shortcuts_for_line)

                '''
                accurracy = 1000000000000
                while len(shortcuts_for_line) < 3 and accurracy > 10000000000:
                    shortcuts_for_line = compute_exact_shortcuts(line=i,accurracy)
                    accurracy = int(accurracy/10)
                '''
                min_x_shortcut = column_nrs[0]
                max_x_shortcut = column_nrs[-1]
                min_y_shortcut = row_nrs[0]
                max_y_shortcut = row_nrs[-1]
                shortcuts_to_remove = []

                # remove shortcuts from outside the possible/valid area
                for x, y in shortcuts_for_line:
                    if x < min_x_shortcut:
                        shortcuts_to_remove.append((x, y))
                    if x > max_x_shortcut:
                        shortcuts_to_remove.append((x, y))
                    if y < min_y_shortcut:
                        shortcuts_to_remove.append((x, y))
                    if y > max_y_shortcut:
                        shortcuts_to_remove.append((x, y))

                for s in shortcuts_to_remove:
                    shortcuts_for_line.remove(s)

                '''
                print('and after:')
                print(len(shortcuts_for_line))

                column_nrs_after = set()
                row_nrs_after = set()
                for x, y in shortcuts_for_line:
                    column_nrs_after.add(x)
                    row_nrs_after.add(y)
                print(column_nrs_after)
                print(row_nrs_after)
                print(shortcuts_for_line)
                '''

                if len(shortcuts_for_line) > len(column_nrs) * len(row_nrs):
                    raise ValueError(
                        'there are more shortcuts than before now. there is something wrong with the algorithm!')
                if len(shortcuts_for_line) < 3:
                    raise ValueError('algorithm not valid! less than 3 zones detected (should be at least 4)')

            else:

                shortcuts_for_line = []
                for column_nr in column_nrs:
                    for row_nr in row_nrs:
                        shortcuts_for_line.append((column_nr, row_nr))

                        # print(shortcuts_for_line)
            for shortcut in shortcuts_for_line:
                shortcuts[shortcut] = shortcuts.get(shortcut, []) + [line]

            line += 1
            # print('collected entries:')
            # print(n)

    print('reading the converted .csv file')
    for ID in _ids():
        nr_of_lines += 1
        zone_ids.append(ID)

    for length in _length_of_rows():
        nr_of_floats += 2 * length

    start_time = datetime.now()
    construct_shortcuts()
    end_time = datetime.now()

    print('calculating the shortcuts took:', end_time - start_time)

    # address where the actual polygon data starts. look in the description below to get more info
    polygon_address = (24 * nr_of_lines + 6)

    # for every original float now 4 bytes are needed (int32)
    shortcut_start_address = polygon_address + 4 * nr_of_floats
    print('The number of polygons is:', nr_of_lines)
    print('The number of floats in all the polygons is (2 per point):', nr_of_floats)
    print('now writing file "', path, '"')
    output_file = open(path, 'wb')
    # write nr_of_lines
    output_file.write(pack(b'!H', nr_of_lines))
    # write start address of shortcut_data:
    output_file.write(pack(b'!I', shortcut_start_address))
    # write zone_ids
    for zone_id in zone_ids:
        output_file.write(pack(b'!H', zone_id))
    # write number of values
    for length in _length_of_rows():
        output_file.write(pack(b'!H', length))

    # write polygon_addresses
    for length in _length_of_rows():
        output_file.write(pack(b'!I', polygon_address))
        # data of the next polygon is at the address after all the space the points take
        # nr of points stored * 2 ints per point * 4 bytes per int
        polygon_address += 8 * length

    if shortcut_start_address != polygon_address:
        # both should be the same!
        raise ValueError('shortcut_start_address and polygon_address should now be the same!')

    # write boundary_data
    for xmax, xmin, ymax, ymin in _boundaries():
        output_file.write(pack(b'!iiii',
                               coord2int(xmax), coord2int(xmin), coord2int(ymax),
                               coord2int(ymin)))

    # write polygon_data
    for x_coords, y_coords in _coordinates():
        for x in x_coords:
            output_file.write(pack(b'!i', coord2int(x)))
        for y in y_coords:
            output_file.write(pack(b'!i', coord2int(y)))

    print('position after writing all polygon data (=start of shortcut section):', output_file.tell())
    # write number of entries in shortcut field (x,y)
    nr_of_entries_in_shortcut = []
    shortcut_entries = []
    total_entries_in_shortcuts = 0

    # count how many shortcut addresses will be written:
    for x in range(360 * NR_SHORTCUTS_PER_LNG):
        for y in range(180 * NR_SHORTCUTS_PER_LAT):
            try:
                this_lines_shortcuts = shortcuts[(x, y)]
                shortcut_entries.append(this_lines_shortcuts)
                total_entries_in_shortcuts += 1
                nr_of_entries_in_shortcut.append(len(this_lines_shortcuts))
                # print((x,y,this_lines_shortcuts))
            except KeyError:
                nr_of_entries_in_shortcut.append(0)

    print('The number of filled shortcut zones are:', total_entries_in_shortcuts)

    if len(nr_of_entries_in_shortcut) != 64800 * NR_SHORTCUTS_PER_LNG * NR_SHORTCUTS_PER_LAT:
        print(len(nr_of_entries_in_shortcut))
        raise ValueError('this number of shortcut zones is wrong')

    # write all nr of entries
    for nr in nr_of_entries_in_shortcut:
        if nr > 300:
            raise ValueError("There are too many polygons in this shortcuts:", nr)
        output_file.write(pack(b'!H', nr))

    # write  Address of first Polygon_nr  in shortcut field (x,y)
    # Attention: 0 is written when no entries are in this shortcut
    shortcut_address = output_file.tell() + 259200 * NR_SHORTCUTS_PER_LNG * NR_SHORTCUTS_PER_LAT
    for nr in nr_of_entries_in_shortcut:
        if nr == 0:
            output_file.write(pack(b'!I', 0))
        else:
            output_file.write(pack(b'!I', shortcut_address))
            # each polygon takes up 2 bytes of space
            shortcut_address += 2 * nr

    # write Line_Nrs for every shortcut
    for entries in shortcut_entries:
        for entry in entries:
            if entry > nr_of_lines:
                raise ValueError(entry)
            output_file.write(pack(b'!H', entry))

    last_address = output_file.tell()
    shortcut_space = last_address - shortcut_start_address
    polygon_space = nr_of_floats * 4

    print('the shortcuts make up', round((shortcut_space / last_address) * 100, 2), '% of the file')
    print('the polygon data makes up', round((polygon_space / last_address) * 100, 2), '% of the file')

    print('Success!')
    return


"""
Data format in the .bin:
IMPORTANT: all coordinates (floats) are converted to int32 (multiplied by 10^7). This makes computations much faster
and it takes lot less space, without loosing too much accuracy (min accuracy is 1cm still at the equator)

no of rows (= no of polygons = no of boundaries)
approx. 28k -> use 2byte unsigned short (has range until 65k)
'!H' = n

I Address of Shortcut area (end of polygons+1) @ 2

'!H'  n times [H unsigned short: zone number=ID in this line, @ 6 + 2* lineNr]

'!H'  n times [H unsigned short: nr of values (coordinate PAIRS! x,y in long long) in this line, @ 6 + 2n + 2* lineNr]

'!I'n times [ I unsigned int: absolute address of the byte where the polygon-data of that line starts,
@ 6 + 4 * n +  4*lineNr]



n times 4 int32 (take up 4*4 per line): xmax, xmin, ymax, ymin  @ 6 + 8n + 16* lineNr
'!iiii'


[starting @ 6+ 24*n = polygon data start address]
(for every line: x coords, y coords:)   stored  @ Address section (see above)
'!i' * amount of points

360 * NR_SHORTCUTS_PER_LNG * 180 * NR_SHORTCUTS_PER_LAT:
[atm: 360* 1 * 180 * 2 = 129,600]
129,600 times !H   number of entries in shortcut field (x,y)  @ Pointer see above


Address of first Polygon_nr  in shortcut field (x,y) [0 if there is no entry] @  Pointer see above + 129,600
129,600 times !I

[X = number of filled shortcuts]
X times !H * amount Polygon_Nr    @ address stored in previous section

"""

if __name__ == '__main__':
    # reading the data from the .json you converted
    parse_polygons_from_json(path='tz_world.json')

    # update all the zone names and set the right ids to be written in the .bin
    update_zone_names(path='timezone_names.py')

    compile_into_binary(path='timezone_data.bin')
