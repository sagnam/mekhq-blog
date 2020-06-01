#!/usr/bin/env python3

# ----------------------------------------------------------------------------
# Basic parameters - change as needed
# ----------------------------------------------------------------------------

#relative or absolute path to your mekhq directory including trailing /
mekhq_path = "/Users/donp/Downloads/mekhq-0.46.1/"

#the name of your campaign file within the campaigns directory of your
#mekhq directory
campaign_file = 'Arts Campaign/Arts Campaign.cpnx'

#change this to choose which personnel get loaded based on personnel types
#in mekhq
#https://github.com/MegaMek/mekhq/blob/master/MekHQ/src/mekhq/campaign/personnel/Person.java#L75
#roles = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,20,22,23,24,25]
roles = [1]

#role names for ALL roles in MekHQ by index number. You can change names, but
#do not remove values, even if you do not use the role above
role_names = ["Mechwarrior", "Aerospace Pilot", "Vehicle Driver", "Naval Vessel Driver", "VTOL Pilot", "Vehicle Gunner", "Battle Armor Infantry", "Conventional Infantry Soldier", "Protomech Pilot", "Conventional Fighter Pilot", "Space Vessel Pilot", "Space Vessel Crew", "Space Vessel Gunner", "Hyperspace Navigator", "Mech Tech", "Mechanic", "Aero Tech", "Battle Armor Tech", "Astech", "Doctor", "Medic", "Admin/Command", "Admin/Logistical", "Admin/Transport", "Admin/HR", "LAM Pilot", "Vehicle Crew"]

#mission, scenario, and personnel status names
mission_status_names = ["Active","Completed","Failed","Breached"]
scenario_status_names = ["Active","Victory","Marginal Victory","Defeat","Marginal Defeat","Draw"]
personnel_status_names = ['Active','Retired','Killed in Action','Missing in Action']
personnel_status_dict = {
    "ACTIVE" : "Active",
    "RETIRED" : "Retired",
    "KIA": "Killed in Action",
    "MIA": "Missing in Action"
}

#skill level names
skill_level_names = ["Ultra-Green","Green","Regular","Veteran","Elite"]

#beginning of portait paths, only change if default image changes
portrait_paths = {
    "default.gif": "default.gif"
}

force_paths = {
}

unit_logo_path = ''

#skill type dictionary
skill_dict = {
}

mech_paths = {
}

fluff_paths = {
}

# ----------------------------------------------------------------------------
# imports
# ----------------------------------------------------------------------------

import xml.etree.ElementTree as ET
import re
import datetime
from dateutil import relativedelta
from html import unescape
import os
import glob
from shutil import copyfile
import javaobj.v2 as javaobj
import zipfile
import tarfile
import time
import json

unitTypes = { 'Mek' : {'combined' : 'pilot'},
            'Tank' : {'combined' : 'pilot'},
            'BattleArmor' : {'combined' : 'men'},
            'Infantry' : {'combined' : 'men'},
            'ProtoMek' : {'combined' : 'pilot'},
            'VTOL' : {'driver' : 'pilot', 'combined' : 'pilot'},
            'Naval' : {'driver' : 'helmsman', 'combined' : 'crew'},
            'Gun Emplacement' : {'driver' : 'crew', 'combined' : 'crew'},
            'Conventional Fighter' : {'driver' : 'pilot', 'combined' : 'pilot'},
            'Aero' : {'driver' : 'pilot', 'combined' : 'pilot'},
            'Small Craft' : {'driver' : 'pilot', 'combined' : 'pilot'},
            'Dropship' : {'driver' : 'pilot', 'combined' : 'crew'},
            'Jumpship' : {'driver' : 'pilot', 'combined' : 'crew'},
            'Warship' : {'driver' : 'pilot', 'combined' : 'crew'},
            'Space Station' : {'driver' : 'pilot', 'combined' : 'crew'}}

# ----------------------------------------------------------------------------
# custom functions
# ----------------------------------------------------------------------------

def load_cache():
    global mech_paths
    cacheFile = mekhq_path + '/data/mechfiles/units.cache'
    lastModified = time.ctime(os.path.getmtime(cacheFile))

    lastModifiedFile = open('unitcache.lastmodified', 'a+')
    lastModifiedFile.seek(0)
    lastLastModified = str(lastModifiedFile.read())

    if (lastModified == lastLastModified):
        unitCache = open('unitcache', 'r')
        mech_paths = json.load(unitCache)
    else:
        unitCache = open('unitcache', 'w+')
        unitCache.truncate(0)
        lastModifiedFile.truncate(0)

        with open(cacheFile, 'rb') as fd:
            javaCacheFile = fd.read()

        javaCache = javaobj.loads(javaCacheFile)

        for cacheEntry in javaCache[1:]:
            if (cacheEntry.m_sChassis is not None):
                unit = cacheEntry.m_sChassis.value

                if (cacheEntry.m_sModel is not None):
                    unit += ' ' + cacheEntry.m_sModel.value

                if (cacheEntry.m_sSourceFile is not None):
                    file = cacheEntry.m_sSourceFile.path.value
                else:
                    file = ''

                if (cacheEntry.m_sEntryName is not None):
                    zipEntry = cacheEntry.m_sEntryName.value
                else:
                    zipEntry = ''

                mech_paths[unit] = [file, zipEntry, cacheEntry.m_sUnitType.value]

        json.dump(mech_paths, unitCache)
        lastModifiedFile.write(lastModified)
    unitCache.close()
    lastModifiedFile.close()

#clean out punctuation and replace spaces with - for url links and slugs
def urlify(s):
    # strip leading and trailing whitespace
    s = s.strip()
    # Remove all non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s]", '', s)
    # Replace all runs of whitespace with a single dash
    s = re.sub(r"\s+", '-', s)
    #slugs have trouble with numbers as the first letter, so add
    #a letter if this is the case
    if(s[0].isdigit()):
        s = "n" + s
    return s.lower()

#takes an xml element and returns either the text of element if it exists
#or an empty string otherwise
def get_xml_text(ele):
    if(ele is not None and ele.text is not None):
        return ele.text
    else:
        return ''

#take an xml element with a date in it and convert to date object
def get_xml_date(ele):
    if(ele is not None and ele.text is not None):
        date  = ele.text.split(" ")[0]
        return datetime.datetime.strptime(date, '%Y-%m-%d')
    else:
        return None

#read portrait pathway. Need to check for special cases
def get_portrait_path(ele):
    path = get_xml_text(ele)
    if(path == '-- General --'):
        return '';
    else:
        return path

#read portrait file. Need to check for special cases
def get_portrait_file(ele):
    file_name = get_xml_text(ele)
    if(file_name == 'None'):
        return '';
    else:
        return file_name

def replace_portrait_name(portrait_file, slug):
    suffix = portrait_file.split('.')[1]
    return slug + '.' + suffix

#read force pathway. Need to check for special cases
def get_force_path(ele):
    path = get_xml_text(ele)
    if(path == '-- General --'):
        return '';
    else:
        return path

#read force file. Need to check for special cases
def get_force_file(ele):
    file_name = get_xml_text(ele)
    if(file_name == 'None'):
        return '';
    else:
        return file_name

def replace_force_name(force_file, slug):
    suffix = force_file.split('.')[1]
    return slug + '.' + suffix

#read force file. Need to check for special cases
def replace_fluff_name(fluff_file, slug):
    suffix = fluff_file.rsplit('.', 1)[1]
    return slug + '.' + suffix

#they switched over from int to enum for status
#so need to consider both ways
def get_person_status(status):
    if(status.isdigit()):
        return personnel_status_names[int(status)]
    else:
        return personnel_status_dict[status]

def get_person_name(person):
    if(person is not None):
        first = get_xml_text(person.find('givenName'))
        surname = get_xml_text(person.find('surname'))
        bloodname = get_xml_text(person.find('bloodname'))
        pilot_name = get_xml_text(person.find('name'))
        if(pilot_name == ''):
            pilot_name = first
            if(surname != ''):
                pilot_name = pilot_name + ' ' + surname
        if(bloodname != ''):
            pilot_name = pilot_name + ' ' + bloodname
        return pilot_name
    return None

#loop through kills and count ones belonging to this uuid
def count_kills(uuid, kills):
  nkills = 0
  for kill in kills.findall('kill'):
    kill_id = kill.find('pilotId')
    if(kill_id is not None and kill_id.text is not None):
      if(uuid == kill_id.text):
       nkills = nkills + 1
  return nkills

# get the name of the unit assigned to person uuid
def get_unit_name(uuid, units):
    for unit in units.findall('unit'):
        if(unit.attrib['id'] == uuid):
            entity = unit.find('entity')
            if(entity is None):
                return ''
            else:
                return entity.attrib['chassis'] + ' ' + entity.attrib['model']
    return None

#loop through units and find the one assigned to a person by uuid
def find_unit(uuid, units):
    for unit in units.findall('unit'):
        for current_id in unit.findall('driverId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
        for current_id in unit.findall('pilotId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
        for current_id in unit.findall('gunnerId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
        for current_id in unit.findall('vesselCrewId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
        for current_id in unit.findall('navigatorId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
        for current_id in unit.findall('techOfficerId'):
            if(current_id is not None and current_id.text is not None and current_id.text == uuid):
                return unit.attrib['id']
    return None

#loop through personnel and find the one assigned to unit by name
def find_person(uuid, personnel):
    for person in personnel.findall('person'):
        current_id = person.attrib['id']
        if(current_id is not None and current_id == uuid):
            return person
    return None

#loop through all the forces identified in element list and output them to
#markdown files. At the end it calls itself to iteratively process the tree
def process_forces(forces_ele, parent_name, parent_slug):
    for force in forces_ele.findall('force'):
        short_force_name = force.find('name').text
        if(parent_name is not None):
            if(parent_name is ''):
                full_force_name = short_force_name
            else:
                full_force_name = parent_name + ', ' + short_force_name
            slug = urlify(full_force_name)
        else:
            #top level force so special things
            full_force_name = ''
            slug = urlify(short_force_name)
        force_desc = get_xml_text(force.find('desc'))
        force_file = get_force_file(force.find('iconFileName'))
        force_path = get_force_path(force.find('iconCategory'))+force_file
        f = open('campaign/_forces/' + slug + '.md', 'w')
        f.write('---\n')
        f.write('layout: force\n')
        f.write('title: ' + short_force_name + '\n')
        f.write('order: ' + force.attrib['id'] + '\n')
        f.write('slug: ' + slug + '\n')

        if(parent_name is not None):
            f.write('parent-name: ' + parent_name + '\n')
            f.write('parent-slug: ' + parent_slug + '\n')

        if(force_path is not '' and force_file is not ''):
            new_force_file = replace_force_name(force_file, slug)
            force_paths[new_force_file] = force_path
            f.write('unit-icon: ' + new_force_file + '\n')

            if(parent_name is None):
                global unit_logo_path
                unit_logo_path = force_path

        f.write('---\n\n')
        f.write(unescape(force_desc))
        f.close()

        subforces = force.find('subforces')
        if(subforces is not None):
            process_forces(subforces, full_force_name, slug)

#loop through forces and find the force that the unit uuid is a member of,
#iteratively recursing through the subforces
def find_force(uuid, forces_ele, parent_name, parent_slug):
    for force in forces_ele.findall('force'):
        short_force_name = force.find('name').text
        if(parent_name is not None):
            if(parent_name is ''):
                full_force_name = short_force_name
            else:
                full_force_name = parent_name + ', ' + short_force_name
            slug = urlify(full_force_name)
        else:
            #top level force so special things
            full_force_name = ''
            slug = urlify(short_force_name)
        units = force.find('units')
        if(units is not None):
            for unit in units.findall('unit'):
                if(unit.attrib['id'] == uuid):
                    return full_force_name
        subforces = force.find('subforces')
        if(subforces is not None):
            found_name = find_force(uuid, subforces, full_force_name, slug)
            if(found_name is not None):
                return found_name
    return None

def find_rank(rank_level, rank_system, role):
    if(role==2 or role==10):
        rank = all_rank_lists[rank_system][1][rank_level]
    elif((role>=3 and role<=6) or role==27):
        rank = all_rank_lists[rank_system][2][rank_level]
    elif(role>=11 and role <=14):
        rank = all_rank_lists[rank_system][3][rank_level]
    elif(role>=7 and role <=8):
        rank = all_rank_lists[rank_system][4][rank_level]
    elif(role>=15 and role <=19):
        rank = all_rank_lists[rank_system][5][rank_level]
    else:
        rank = all_rank_lists[rank_system][0][rank_level]
    rank = check_rank(rank, rank_level, all_rank_lists[rank_system])
    if(rank == '-' or rank == "None"):
        return None
    else:
        return rank

def check_rank(rank, rank_level, rank_list):
    if(rank == '--MW'):
        rank = rank_list[0][rank_level]
    elif(rank == '--ASF'):
        rank = rank_list[1][rank_level]
    elif(rank == '--VEE'):
        rank = rank_list[2][rank_level]
    elif(rank == '--NAVAL'):
        rank = rank_list[3][rank_level]
    elif(rank == '--INF'):
        rank = rank_list[4][rank_level]
    elif(rank == '--TECH'):
        rank = rank_list[5][rank_level]
    else:
        return rank
    return check_rank(rank, rank_level, rank_list)

def process_rank_system(rsystem):
    rank_mw    = []
    rank_asf   = []
    rank_vee   = []
    rank_naval = []
    rank_inf   = []
    rank_tech  = []
    for rank in rsystem.findall("rank"):
        rank_names = get_xml_text(rank.find('rankNames')).split(",")
        rank_mw.append(rank_names[0])
        rank_asf.append(rank_names[1])
        rank_vee.append(rank_names[2])
        rank_naval.append(rank_names[3])
        rank_inf.append(rank_names[4])
        rank_tech.append(rank_names[5])
    return [rank_mw, rank_asf, rank_vee, rank_naval, rank_inf, rank_tech]

#custom class for skill type
class SkillType:
    def __init__(self, name, target, count_up, green, reg, vet, elite):
        self.name = name
        self.target = target
        self.count_up = count_up
        self.green = green
        self.reg = reg
        self.vet = vet
        self.elite = elite

    def get_target_desc(self, skill):
        if(self.count_up):
            value = self.target + skill.level + skill.bonus
            return '+' + str(value)
        else:
            value = self.target - (skill.level  + skill.bonus)
            return str(value) + '+'

    def get_skill_level(self, level):
        if(level >= self.elite):
            return 4
        elif(level >= self.vet):
            return 3
        elif(level >= self.reg):
            return 2
        elif(level >= self.green):
            return 1
        else:
            return 0

class Skill:
    def __init__(self, name, level, bonus):
        self.name = name
        self.level = level
        self.bonus = bonus

def get_skill_desc(sk1, sk2):
    if(sk1 is None):
        return None
    lvl = skill_dict[sk1.name].get_skill_level(sk1.level)
    tgt_desc = skill_dict[sk1.name].get_target_desc(sk1)
    if(sk2 is not None):
        lvl2 = skill_dict[sk2.name].get_skill_level(sk2.level)
        lvl = int((lvl+lvl2)/2)
        tgt_desc = tgt_desc + "/" + skill_dict[sk2.name].get_target_desc(sk2)
        tgt_desc = re.sub(r"\+", '', tgt_desc)
    return [skill_level_names[lvl], tgt_desc]

def get_skill_report(person):
    role = int(person.find('primaryRole').text)
    skills = {}
    for skill in person.findall('skill'):
        sk_name = get_xml_text(skill.find('type'))
        sk_lvl = int(get_xml_text(skill.find('level')))
        sk_bns = int(get_xml_text(skill.find('bonus')))
        skills[sk_name] = Skill(sk_name, sk_lvl, sk_bns)
    sk1 = None
    sk2 = None
    if(role == 1): #mechwarrior
        if('Gunnery/Mech' in skills):
            sk1 = skills['Gunnery/Mech']
        if('Piloting/Mech' in skills):
            sk2 = skills['Piloting/Mech']
    elif(role == 2): #ASF pilot
        if('Gunnery/Aerospace' in skills):
            sk1 = skills['Gunnery/Aerospace']
        if('Piloting/Aerospace' in skills):
            sk2 = skills['Piloting/Aerospace']
    elif(role == 3): #vee driver
        if('Piloting/Ground Vehicle' in skills):
            sk1 = skills['Piloting/Ground Vehicle']
    elif(role == 4): #bluewater naval driver
        if('Piloting/Naval' in skills):
            sk1 = skills['Piloting/Naval']
    elif(role == 5): #VTOL pilot
        if('Piloting/VTOL' in skills):
            sk1 = skills['Piloting/VTOL']
    elif(role == 6): #Vee gunner
        if('Gunnery/Vehicle' in skills):
            sk1 = skills['Gunnery/Vehicle']
    elif(role == 7): #BA pilot
        if('Gunnery/Battlesuit' in skills):
            sk1 = skills['Gunnery/Battlesuit']
        if('Anti-Mech' in skills):
            sk2 = skills['Anti-Mech']
    elif(role == 8): #Conventional Infantry
        if('Small Arms' in skills):
            sk1 = skills['Small Arms']
    elif(role == 9): #Protomech Pilot
        if('Gunnery/Protomech' in skills):
            sk1 = skills['Gunnery/Protomech']
    elif(role == 10): #Conv Fighter Pilot
        if('Gunnery/Aircraft' in skills):
            sk1 = skills['Gunnery/Aircraft']
        if('Piloting/Jet' in skills):
            sk2 = skills['Piloting/Jet']
    elif(role == 11): #Space pilot
        if('Piloting/Aircraft' in skills):
            sk1 = skills['Piloting/Spacecraft']
    elif(role == 12): #space crew
        if('Tech/Vessel' in skills):
            sk1 = skills['Tech/Vessel']
    elif(role == 13): #space gunners
        if('Gunnery/Spacecraft' in skills):
            sk1 = skills['Gunnery/Spacecraft']
    elif(role == 14): #Navigator
        if('Hyperspace Navigator' in skills):
            sk1 = skills['Hyperspace Navigation']
    elif(role == 15): #Mech Tech
        if('Tech/Mech' in skills):
            sk1 = skills['Tech/Mech']
    elif(role == 16): #Mechanic Tech
        if('Tech/Mechanic' in skills):
            sk1 = skills['Tech/Mechanic']
    elif(role == 17): #Aero Tech
        if('Tech/Aero' in skills):
            sk1 = skills['Tech/Aero']
    elif(role == 18): #BA Tech
        if('Tech/BA' in skills):
            sk1 = skills['Tech/BA']
    elif(role == 19): #Astech
        if('Astech' in skills):
            sk1 = skills['Astech']
    elif(role == 20): #Doctor
        if('Doctor' in skills):
            sk1 = skills['Doctor']
    elif(role == 21): #Medic
        if('Medtech' in skills):
            sk1 = skills['Medtech']
    elif(role >= 22 and role <=25): #Admin
        if('Administration' in skills):
            sk1 = skills['Administration']
    return get_skill_desc(sk1, sk2)


def process_mech_file(f, name, raw_content):
    content = ['<p>']
    for line in raw_content.split('\n'):
        if (':' in line):
            if (line.startswith('imagefile:')):
                fluff_file = line.split(':')[1]
                new_fluff_file = replace_fluff_name(fluff_file, urlify(name))
                fluff_paths[new_fluff_file] = fluff_file
                f.write('fluff: ' + new_fluff_file + '\n')
            else:
                content += ['<b>' + line.replace(':', ':</b> ') + '<br/>\n']
        else:
            content += [line  + '<br/>\n']
    content += ['</p>']

    f.write('---\n')
    for line in content:
        f.write(line)
    return content

# ----------------------------------------------------------------------------
# Remove old files to start fresh
# ----------------------------------------------------------------------------

files = glob.glob('campaign/_forces/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_missions/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_personnel/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_scenarios/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_tro/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_parts/*')
for f in files:
    os.remove(f)

files = glob.glob('campaign/_finances/*')
for f in files:
    os.remove(f)

files = glob.glob('assets/images/portraits/*')
for f in files:
    os.remove(f)

files = glob.glob('assets/images/force/*')
for f in files:
    os.remove(f)

# ----------------------------------------------------------------------------
# Load the file and top-level information
# ----------------------------------------------------------------------------

tree = ET.parse(mekhq_path + 'campaigns/' + campaign_file)
campaign = tree.getroot()

#stuff we need
campaign_info = campaign.find('info')
date = datetime.datetime.strptime(campaign_info.find('calendar').text, '%Y-%m-%d %H:%M:%S')
kills = campaign.find('kills')
skill_types = campaign.find('skillTypes')
personnel = campaign.find('personnel')
missions = campaign.find('missions')
forces = campaign.find('forces')
units = campaign.find('units')
customs = campaign.findall('custom')
parts = campaign.find('parts')
finances = campaign.find('finances')

# ----------------------------------------------------------------------------
# Load unit list from cache (or refresh if source units.cache has changed)
# ----------------------------------------------------------------------------
load_cache()

# ----------------------------------------------------------------------------
# Process default and custom rank structure and skill types for later use
# ----------------------------------------------------------------------------

rank_tree = ET.parse(mekhq_path + 'data/universe/ranks.xml')
rank_systems = rank_tree.getroot()
all_rank_lists = []
for rank_system in rank_systems.findall('rankSystem'):
    all_rank_lists.append(process_rank_system(rank_system))

#now check for a custom rank system to append
#custom is hard-coded to 12
rank_system = campaign_info.find('rankSystem')
all_rank_lists[12] = process_rank_system(rank_system)
rank_system_default = int(get_xml_text(rank_system.find("system")))


#process skill types
for skill_type in skill_types.findall("skillType"):
    skill_name = get_xml_text(skill_type.find('name'))
    skill_target = int(get_xml_text(skill_type.find('target')))
    skill_count_up = get_xml_text(skill_type.find('countUp')) == 'true'
    skill_green = int(get_xml_text(skill_type.find('greenLvl')))
    skill_reg = int(get_xml_text(skill_type.find('regLvl')))
    skill_vet = int(get_xml_text(skill_type.find('vetLvl')))
    skill_elite = int(get_xml_text(skill_type.find('eliteLvl')))
    skill_dict[skill_name] = SkillType(skill_name, skill_target, skill_count_up, skill_green, skill_reg, skill_vet, skill_elite)

# ----------------------------------------------------------------------------
# Process the xml and output results to campaign directory
# ----------------------------------------------------------------------------

# process forces
process_forces(forces, None, None)

#loop through personnel and print out markdown file for each one
for person in personnel.findall('person'):
    uuid  = person.find('id').text
    primary_role = int(person.find('primaryRole').text)
    role_name = role_names[primary_role-1]
    first = get_xml_text(person.find('givenName'))
    surname = get_xml_text(person.find('surname'))
    bloodname = get_xml_text(person.find('bloodname'))
    name = get_xml_text(person.find('name'))
    if(name == ''):
        name = first
        if(surname != ''):
            name = name + ' ' + surname
    if(bloodname != ''):
        name = name + ' ' + bloodname
    status = get_person_status(get_xml_text(person.find('status')))
    birthdate = get_xml_date(person.find('birthday'))
    deathdate = get_xml_date(person.find('deathday'))
    clan = get_xml_text(person.find('clan')) == 'true'
    phenotype = get_xml_text(person.find('phenotype'))
    if(clan):
        if(phenotype == '0' or phenotype == ''):
            phenotype = 'Freeborn Clan'
        else:
            phenotype = 'Trueborn Clan'
    else:
        phenotype = ''
    rank_number = get_xml_text(person.find('rank'))
    person_rank_system = get_xml_text(person.find('rankSystem'))
    if(person_rank_system == '' or person_rank_system == '-1'):
        person_rank_system = rank_system_default
    else:
        person_rank_system = int(person_rank_system)
    if(rank_number is not None):
        rank_name = find_rank(int(rank_number), person_rank_system, primary_role)
    unit_id = find_unit(uuid, units)
    unit_name = None
    force_name = None
    if(unit_id is not None):
        unit_name = get_unit_name(unit_id, units)
        force_name = find_force(unit_id, forces, None, None)
    dead = deathdate is not None
    if(dead):
        age = relativedelta.relativedelta(deathdate, birthdate).years
    else:
        age = relativedelta.relativedelta(date, birthdate).years
    if primary_role in roles and name is not '':
        title = name
        if(rank_name is not None):
            title = rank_name + ' ' + name
        bio = get_xml_text(person.find('biography'))
        skill_desc = get_skill_report(person)
        kill_count = count_kills(uuid, kills)
        portrait_file = get_portrait_file(person.find('portraitFile'))
        portrait_path = get_portrait_path(person.find('portraitCategory'))+portrait_file
        callsign = get_xml_text(person.find('callsign'))
        f = open('campaign/_personnel/' + urlify(name) + '.md', 'w')
        f.write('---\n')
        f.write('layout: bio\n')
        f.write('title: ' + title + '\n')
        f.write('name: ' + name + '\n')
        f.write('status: ' + status + '\n')
        if(phenotype != ''):
            f.write('phenotype: ' + phenotype + '\n')
        f.write('role: ' + str(primary_role) + '\n')
        f.write('role-name: ' + role_name + '\n')
        if(skill_desc is not None):
            f.write('skill-level: ' + skill_desc[0] + '\n')
            f.write('skill-detail: ' + skill_desc[1] + '\n')
        if(callsign != ''):
            f.write('callsign: ' + callsign + '\n')
        if(kill_count>0):
            f.write('kills: ' + str(kill_count) + '\n')
        f.write('age: ' + str(age) + '\n')
        if(rank_number is not None):
            f.write('rank-number: ' + rank_number + '\n')
        if(rank_name is not None):
            f.write('rank-name: ' + rank_name + '\n')
        if(unit_name is not None):
            f.write('unit: ' + unit_name + '\n')
            f.write('unit-id: ' + unit_id + '\n')
            f.write('unit-slug: ' + urlify(unit_name) + '\n')
        f.write('slug: ' + urlify(name) + '\n')
        if(force_name is not None):
            f.write('force: ' + force_name + '\n')
            f.write('force-slug: ' + urlify(force_name) + '\n')
        if(portrait_path is not '' and portrait_file is not ''):
            new_portrait_file = replace_portrait_name(portrait_file, urlify(name))
            portrait_paths[new_portrait_file] = portrait_path
            f.write('portrait: ' + new_portrait_file + '\n')
        f.write('---\n\n')
        f.write(unescape(bio))
        f.close()


#loop through units and print out markdown file for each one
for unit in units.findall('unit'):
    entity = unit.find('entity')
    refit = unit.find('refit')
    if (refit is not None):
        refitEntity = refit.find('entity')
        name = refitEntity.attrib.get('chassis') + ' ' + refitEntity.attrib.get('model')
    else:
        name = entity.attrib.get('chassis') + ' ' + entity.attrib.get('model')

    salvage = unit.find('salvaged').text
    f = open('campaign/_tro/' + urlify(name) + '.md', 'w')
    f.write('---\n')
    f.write('layout: unit\n')
    f.write('name: ' + name + '\n')
    f.write('slug: ' + urlify(name) + '\n')
    f.write('salvage: ' + salvage + '\n')
    if (refit is not None):
        f.write('refit: true\n')

    mechInfo = mech_paths[name]
    if (mechInfo is not None):
        allPeople = {'pilot':[],'crew':[],'men':[],'helmsman':[]}
        crewRoles = [['driver','driverId'],['gunner','gunnerId'],['vesselCrew','vesselCrewId'],['navigator','navigatorId'],['techOfficer','techOfficerId']]
        for crewRole in crewRoles:
            allPeople[crewRole[0]] = []
            for person_id in unit.findall(crewRole[1]):
                if(person_id is not None):
                    roleOverride = crewRole[0]
                    if (crewRole[0] in unitTypes[mechInfo[2]]):
                        roleOverride = unitTypes[mechInfo[2]][crewRole[0]]
                    allPeople[roleOverride] += [person_id.text]

        dupeRole = 'driver'
        if ('driver' in unitTypes[mechInfo[2]]):
            dupeRole = unitTypes[mechInfo[2]]['driver']

        for gunner in allPeople['gunner'][:]:
            if (gunner in allPeople[dupeRole]):
                if (gunner not in allPeople[unitTypes[mechInfo[2]]['combined']]):
                    allPeople[unitTypes[mechInfo[2]]['combined']] += [gunner]
                allPeople['gunner'].remove(gunner)
                if (gunner in allPeople['driver']):
                    allPeople['driver'].remove(gunner)

        for crewRole in allPeople:
            people = allPeople[crewRole]
            if (len(people) > 0):
                f.write(crewRole + 'List:\n')
                for person_id in people:
                    person = find_person(person_id, personnel)
                    person_name = get_person_name(person)
                    if(person_name is not None):
                        f.write('- {name: ' + person_name + ', slug: ' + urlify(person_name) + '}\n')

        unit_id = unit.attrib.get('id')
        force_name = find_force(unit_id, forces, None, None)
        if(force_name is not None):
            f.write('force: ' + force_name + '\n')
            f.write('force-slug: ' + urlify(force_name) + '\n')

        content = ['No TRO available']
        mechFilePath = mekhq_path + mechInfo[0]
        if (tarfile.is_tarfile(mechFilePath)):
            tarFile = tarfile.open(mechFilePath)
            mechTarFile = tarFile.getmember(mechInfo[1])
            reader = tarFile.extractfile(mechTarFile)
            raw_content = reader.read().decode("utf-8")
            content = process_mech_file(f, name, raw_content)

        elif zipfile.is_zipfile(mechFilePath):
            zipFile = zipfile.ZipFile(mechFilePath)
            mechZipFile = zipFile.open(mechInfo[1])
            raw_content = mechZipFile.read().decode("utf-8")
            content = process_mech_file(f, name, raw_content)
        else:
            mechFile = open(mechFilePath, 'r')
            raw_content = mechFile.read()
            content = process_mech_file(f, name, raw_content)

    f.close()

#loop through parts and print out markdown file for all
f = open('campaign/_parts/parts.md', 'w')
f.write('---\n')
f.write('layout: parts\n')
f.write('---\n\n')
f.write('<table class="sorttable">\n')
f.write('\t<tr>\n')
f.write('\t\t<th><a href="#" class="sort-by">Name</a></th>\n')
f.write('\t\t<th><a href="#" class="sort-by">Type</a></th>\n')
f.write('\t\t<th><a href="#" class="sort-by">Quantity</a></th>\n')
f.write('\t\t<th><a href="#" class="sort-by">Weight</a></th>\n')
f.write('\t\t<th><a href="#" class="sort-by">Detail</a></th>\n')
f.write('\t\t<th><a href="#" class="sort-by">Status</a></th>\n')
f.write('\t</tr>\n')

for part in parts.findall('part'):
    type = part.attrib.get('type')
    name = part.find('name')
    amount = part.find('amount')
    weight = part.find('equipTonnage')
    unitId = part.find('unitId')
    typeName = part.find('typeName')
    clan = part.find('clan')
    forWeight = part.find('unitTonnage')
    reserved = part.find('refitId')
    damaged = part.find('hits')
    munition = part.find('munition')
    shots = part.find('shots')

    # for some reason there is a bunch of battle armor armor in the campaign
    # file but not in the warehouse
    if(unitId is None and name is not None and type != 'mekhq.campaign.parts.BaArmor'):
        f.write('\t<tr>\n')
        f.write('\t\t<td>' + name.text + '</td>\n')

        if ((clan is not None) and (clan.text == 'true')) or ((typeName is not None) and (typeName.text.startswith('CL'))):
            f.write('\t\t<td>Clan</td>\n')
        else:
            f.write('\t\t<td>IS</td>\n')

        if (amount is not None):
            f.write('\t\t<td>' + amount.text + '</td>\n')
        elif (munition is not None and shots is not None):
            f.write('\t\t<td>' + shots.text + '</td>\n')
        else:
            f.write('\t\t<td>1</td>\n')

        if (weight is not None):
            f.write('\t\t<td>' + str(round(float(weight.text),1)) + '</td>\n')
        elif (munition is not None and forWeight is not None and
                (type != 'mekhq.campaign.parts.equipment.AmmoBin')):
            f.write('\t\t<td>' + forWeight.text + '</td>\n')
            forWeight = None
        else:
            f.write('\t\t<td></td>\n')

        if (((type == 'mekhq.campaign.parts.MekLocation') or
            (type == 'mekhq.campaign.parts.equipment.JumpJet') or
            (type == 'mekhq.campaign.parts.MekSensor') or
            (type == 'mekhq.campaign.parts.MekActuator') or
            (type == 'mekhq.campaign.parts.EnginePart')) and
            (forWeight is not None)):
            f.write('\t\t<td>' + forWeight.text + ' tons</td>\n')
        else:
            f.write('\t\t<td></td>\n')

        if (reserved is not None and reserved.text != 'null'):
            f.write('\t\t<td>reserved</td>\n')
        elif (damaged is not None and damaged.text != '0'):
            f.write('\t\t<td>damaged</td>\n')
        else:
            f.write('\t\t<td></td>\n')


        f.write('\t</tr>\n')

f.write('</table>\n')
f.close()


#loop through missions and scenarios. Use slugs to link scenarios
#to mission, but actually linking will be done by liquid
for mission in missions.findall('mission'):
    mission_name = mission.find('name').text
    mission_type = get_xml_text(mission.find('type'))
    mission_desc = get_xml_text(mission.find('desc'))
    mission_id = int(mission.attrib['id'])*10
    mission_start = get_xml_date(mission.find('startDate'))
    mission_end = get_xml_date(mission.find('endDate'))
    mission_employer = get_xml_text(mission.find('employer'))
    mission_location = get_xml_text(mission.find('systemId'))
    mission_status = get_xml_text(mission.find('status'))
    f = open('campaign/_missions/' + urlify(mission_name) + '.md', 'w')
    f.write('---\n')
    f.write('layout: mission\n')
    f.write('title: ' + mission_name + '\n')
    if(mission_start is not None):
        f.write('start-date: ' + mission_start.strftime('%Y-%m-%d') + '\n')
    if(mission_end is not None):
        f.write('end-date: ' + mission_end.strftime('%Y-%m-%d') + '\n')
    if(mission_type != ''):
        f.write('type: ' + mission_type + '\n')
    if(mission_employer != ''):
        f.write('employer: ' + mission_employer + '\n')
    if(mission_location != ''):
        f.write('location: ' + mission_location + '\n')
    if(mission_status != ''):
        f.write('status: ' + mission_status_names[int(mission_status)] + '\n')
    f.write('mission-order: ' + str(mission_id) + '\n')
    f.write('slug: ' + urlify(mission_name) + '\n')
    f.write('---\n\n')
    f.write(unescape(mission_desc))
    f.close()
    scenarios = mission.find('scenarios')
    if(scenarios is not None):
        for scenario in scenarios.findall('scenario'):
            scenario_name = scenario.find('name').text
            scenario_desc = get_xml_text(scenario.find('desc'))
            scenario_aar = get_xml_text(scenario.find('report'))
            scenario_date = get_xml_date(scenario.find('date'))
            scenario_status = get_xml_text(scenario.find('status'))
            f = open('campaign/_scenarios/' + urlify(mission_name + ' ' + scenario_name) + '.md', 'w')
            f.write('---\n')
            f.write('layout: mission\n')
            f.write('title: ' + scenario_name + '\n')
            if(scenario_date is not None):
                f.write('date: ' + scenario_date.strftime('%Y-%m-%d') + '\n')
            if(scenario_status != ''):
                f.write('status: ' + scenario_status_names[int(scenario_status)] + '\n')
            f.write('mission: ' + mission_name + '\n')
            f.write('mission-slug: ' + urlify(mission_name) + '\n')
            f.write('---\n\n')
            f.write(scenario_desc + '\n')
            if(scenario_aar is not ''):
                f.write('\n##### After-Action Report\n\n')
                f.write(scenario_aar)
            f.close()

#loop through transations and print out markdown file for all
content = ['<table class="sorttable">\n']
content += ['\t<tr>\n']
content += ['\t\t<th><a href="#" class="sort-by">Description</a></th>\n']
content += ['\t\t<th><a href="#" class="sort-by">Amount</a></th>\n']
content += ['\t\t<th><a href="#" class="sort-by">Date</a></th>\n']
content += ['\t</tr>\n']

funds = 0
for transation in finances.findall('transaction'):
    description = transation.find('description')
    amountStr = transation.find('amount')
    date = transation.find('date')
    amount = int(amountStr.text.split()[0])
    funds += amount
    content += ['\t<tr>\n']
    content += ['\t\t<td>' + description.text + '</td>\n']
    content += ['\t\t<td>' + f'{amount:,}' + '</td>\n']
    content += ['\t\t<td>' + date.text + '</td>\n']
    content += ['\t</tr>\n']

# content += ['\t</tbody>\n']
content += ['</table>\n']

f = open('campaign/_finances/finances.md', 'w')

f.write('---\n')
f.write('layout: finances\n')
f.write('funds: ' + f'{funds:,}' + ' CBills\n')
f.write('---\n\n')
for line in content:
    f.write(line)
f.close()


# ----------------------------------------------------------------------------
# Copy over data from MekHQ
# ----------------------------------------------------------------------------

#copy over images
for portrait_name in portrait_paths:
    portrait_path = portrait_paths[portrait_name]
    try:
        copyfile(mekhq_path + 'data/images/portraits/' + portrait_path, 'assets/images/portraits/' + portrait_name)
    except:
        pass

#copy over images
for force_name in force_paths:
    force_path = force_paths[force_name]
    try:
        copyfile(mekhq_path + 'data/images/force/' + force_path, 'assets/images/force/' + force_name)
    except:
        pass

#copy over unit logo
if(unit_logo_path is not ''):
    try:
        copyfile(mekhq_path + 'data/images/force/' + unit_logo_path, 'assets/images/unit_logo.jpg')
    except:
        pass


def find_sensitive_path(dir, insensitive_path):
    insensitive_path = insensitive_path.strip(os.path.sep)

    parts = insensitive_path.split(os.path.sep)
    next_name = parts[0]
    for name in os.listdir(dir):
        if next_name.lower() == name.lower():
            improved_path = os.path.join(dir, name)
            if len(parts) == 1:
                return improved_path
            else:
                return find_sensitive_path(improved_path, os.path.sep.join(parts[1:]))
    return None

#copy over fluff images
for fluff_name in fluff_paths:
    fluff_path = fluff_paths[fluff_name]
    try:
        path = find_sensitive_path(mekhq_path, fluff_path.strip('.').replace("\\","/"))
        copyfile(path, 'assets/images/fluff/' + fluff_name)
    except:
        pass
