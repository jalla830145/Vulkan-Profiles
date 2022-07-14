#!/usr/bin/python3
#
# Copyright (c) 2022 LunarG, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Ziga Markus <ziga@lunarg.com>

from datetime import datetime
import argparse
import json
import genvp
import re
import os
import collections

class ProfileMerger():
    def __init__(self, registry):
        self.registry = registry

    def merge(self, jsons, profiles, profile_names, merged_path, merged_profile, mode):
        self.mode = mode

        # Find the api version to use
        api_version = self.get_api_version(profiles)

        # Begin constructing merged profile
        merged = dict()
        merged['$schema'] = self.get_schema(jsons)
        merged['capabilities'] = self.merge_capabilities(jsons, profile_names, api_version[1])

        profile_description = self.get_profile_description(profile_names, mode)
        merged['profiles'] = self.get_profiles(merged_profile, api_version[0], profile_description)

        # Wite new merged profile
        with open(merged_path, 'w') as file:
            json.dump(merged, file, indent = 4)

    def get_schema(self, jsons):
        # Take higher version of the schema
        version = self.get_version_from_schema(jsons[0]['$schema'])
        for json in jsons:
            current_version = self.get_version_from_schema(json['$schema'])
            for i in range(len(version)):
                if (current_version[i] > version[i]):
                    version = current_version
                    break
                elif (current_version[i] < version[i]):
                    break
        return 'https://schema.khronos.org/vulkan/profiles-' + version[0] + '.' + version[1] + '.' + version[2] + '-' + version[3] + '.json#'

    def merge_capabilities(self, jsons, profile_names, api_version):
        merged_extensions = dict()
        merged_features = dict()
        merged_properties = dict()
        merged_formats = dict()
        merged_qfp = list()

        for i in range(len(jsons)):
            self.first = i == 0
            for capability_name in jsons[i]['profiles'][profile_names[i]]['capabilities']:
                capability = jsons[i]['capabilities'][capability_name]

                # Removed feature and properties not in the current json from already merged dicts
                if self.mode == 'intersection' and self.first is False:
                    if 'features' in capability:
                        for feature in dict(merged_features):
                            if feature not in capability['features']:
                                del merged_features[feature]
                    else:
                        merged_features.clear()

                    if 'properties' in capability:
                        for property in dict(merged_properties):
                            if property not in capability['properties']:
                                del merged_properties[property]
                    else:
                        merged_properties.clear()

                if 'extensions' in capability:
                    if self.mode == 'union' or self.first:
                        for extension in capability['extensions']:
                            # vk_version = self.get_promoted_version(self.registry.extensions[extension].promotedTo)
                            # Check if the extension was not promoted in the version used
                            # if vk_version is None or (vk_version[0] > api_version[0]) or (vk_version[0] == api_version[0] and vk_version[1] > api_version[1]):
                            merged_extensions[extension] = capability['extensions'][extension]
                    else:
                        for extension in list(merged_extensions):
                            if not extension in capability['extensions']:
                                del merged_extensions[extension]
                if 'features' in capability:
                    for feature in capability['features']:
                        # Feature already exists, add or overwrite members
                        if feature in merged_features:
                            self.add_struct(feature, capability['features'][feature], merged_features)
                        else:
                            written = False
                            # Check if the promoted struct of current feature was already added
                            promoted_struct = self.get_promoted_struct_name(feature, True)
                            if promoted_struct and promoted_struct in merged_features:
                                self.add_members(merged_features[promoted_struct], capability['features'][feature])
                                written = True
                            # If this is a promoted struct, check if any structs already exists which are extension struct that are promoted to this struct
                            elif promoted_struct == feature:
                                # Add this structure
                                self.add_struct(feature, capability['features'][feature], merged_features)
                                # Combine all other extension structures (which are promoted to this version) into this structure
                                self.promote_structs(feature, merged_features, True)
                                written = True
                            if not written:
                                aliases = self.registry.structs[feature].aliases
                                for alias in aliases:
                                    if alias in merged_features:
                                        # Alias is already set, find which one to use
                                        struct = self.find_higher_struct(feature, alias)
                                        if struct == feature:
                                            merged_features[feature] = merged_features.pop(alias)
                                            self.add_members(merged_features[feature], capability['features'][feature])
                                        if struct == alias:
                                            self.add_members(merged_features[alias], capability['features'][feature])
                                        written = True
                                        break
                            if not written:
                                self.add_struct(feature, capability['features'][feature], merged_features)

                if 'properties' in capability:
                    for property in capability['properties']:
                        # Property already exists, add or overwrite members
                        if property in merged_properties:
                            self.add_members(merged_properties[property], capability['properties'][property], property)
                        else:
                            # Check if the promoted struct of current property was already added
                            promoted_struct = self.get_promoted_struct_name(property, True)
                            if promoted_struct and promoted_struct in merged_properties:
                                self.add_members(merged_properties[promoted_struct], capability['properties'][property])
                            # If this is a promoted struct, check if any structs already exists which are extension struct that are promoted to this struct
                            elif promoted_struct == property:
                                # Add this structure
                                self.add_struct(property, capability['properties'][property], merged_properties)
                                # Combine all other extension structures (which are promoted to this version) into this structure
                                self.promote_structs(feature, merged_properties, True)
                            else:
                                aliases = self.registry.structs[property].aliases
                                for alias in aliases:
                                    if alias in merged_properties:
                                        # Alias is already set, find which one to use
                                        struct = self.find_higher_struct(property, alias)
                                        if struct == property:
                                            merged_properties[property] = merged_properties.pop(alias)
                                            self.add_members(merged_properties[property], capability['properties'][property])
                                        if struct == alias:
                                            self.add_members(merged_properties[alias], capability['properties'][property])
                                        break
                                self.add_struct(property, capability['properties'][property], merged_properties)
                if 'formats' in capability:
                    for format in capability['formats']:
                        if format not in merged_formats:
                            merged_formats[format] = dict()
                            merged_formats[format]['VkFormatProperties'] = dict()
                        self.merge_format_features(merged_formats, format, capability, 'linearTilingFeatures')
                        self.merge_format_features(merged_formats, format, capability, 'optimalTilingFeatures')
                        self.merge_format_features(merged_formats, format, capability, 'bufferFeatures')
                        # Remove empty entries (can occur when using intersect)
                        if not dict(merged_formats[format]['VkFormatProperties']):
                            del merged_formats[format]

                if 'queueFamiliesProperties' in capability:
                    if self.mode == 'intersection':
                        # If this is the first json just append all queue family properties
                        if self.first:
                            for qfp in capability['queueFamiliesProperties']:
                                merged_qfp.append(qfp)
                        # Otherwise do an intersect
                        else:
                            for mqfp in list(merged_qfp):
                                found = False
                                #if self.compareList(mqfp['VkQueueFamilyProperties']['queueFlags'], qfp['VkQueueFamilyProperties']['queueFlags']):
                                #    found = True
                                #    if (qfp['VkQueueFamilyProperties']['queueCount'] < mqfp['VkQueueFamilyProperties']['queueCount']):
                                #        mqfp['VkQueueFamilyProperties']['queueCount'] = qfp['VkQueueFamilyProperties']['queueCount']
                                #    if (qfp['VkQueueFamilyProperties']['timestampValidBits'] < mqfp['VkQueueFamilyProperties']['timestampValidBits']):
                                #        mqfp['VkQueueFamilyProperties']['timestampValidBits'] = qfp['VkQueueFamilyProperties']['timestampValidBits']
                                #    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width'] > mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width']):
                                #        mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width'] = qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width']
                                #    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height'] > mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height']):
                                #        mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height'] = qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height']
                                #    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth'] > mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth']):
                                #        mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth'] = qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth']
                                for qfp in capability['queueFamiliesProperties']:
                                    if mqfp['VkQueueFamilyProperties']['queueFlags'] != qfp['VkQueueFamilyProperties']['queueFlags']:
                                        continue
                                    if (qfp['VkQueueFamilyProperties']['queueCount'] != mqfp['VkQueueFamilyProperties']['queueCount']):
                                        continue
                                    if (qfp['VkQueueFamilyProperties']['timestampValidBits'] != mqfp['VkQueueFamilyProperties']['timestampValidBits']):
                                        continue
                                    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width']):
                                        continue
                                    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height']):
                                        continue
                                    if (qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth']):
                                        continue
                                    found = True
                                if not found:
                                    merged_qfp.remove(mqfp)
                                    
                    elif self.mode == 'union':
                        for qfp in capability['queueFamiliesProperties']:
                            if not merged_qfp:
                                merged_qfp.append(qfp)
                            else:
                                for mqfp in merged_qfp:
                                    if not self.compareList(mqfp['VkQueueFamilyProperties']['queueFlags'], qfp['VkQueueFamilyProperties']['queueFlags']):
                                        merged_qfp.append(qfp)
                                    elif qfp['VkQueueFamilyProperties']['queueCount'] != mqfp['VkQueueFamilyProperties']['queueCount']:
                                        merged_qfp.append(qfp)
                                    elif qfp['VkQueueFamilyProperties']['timestampValidBits'] != mqfp['VkQueueFamilyProperties']['timestampValidBits']:
                                        merged_qfp.append(qfp)
                                    elif qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['width']:
                                        merged_qfp.append(qfp)
                                    elif qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['height']:
                                        merged_qfp.append(qfp)
                                    elif qfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth'] != mqfp['VkQueueFamilyProperties']['minImageTransferGranularity']['depth']:
                                        merged_qfp.append(qfp)

                    else:
                        print("ERROR: Unknown combination mode: " + self.mode)

        capabilities = dict()
        capabilities['baseline'] = dict()
        if merged_extensions:
            capabilities['baseline']['extensions'] = merged_extensions
        if merged_features:
            capabilities['baseline']['features'] = merged_features
        if merged_properties:
            capabilities['baseline']['properties'] = merged_properties
        if merged_formats:
            capabilities['baseline']['formats'] = merged_formats
        if merged_qfp:
            capabilities['baseline']['queueFamiliesProperties'] = merged_qfp

        return capabilities

    def compareList(self, l1, l2):
        return collections.Counter(l1) == collections.Counter(l2)

    def merge_format_features(self, merged_formats, format, capability, features):
        # Remove all format features not in current json if intersect is used
        if self.mode == 'intersection' and self.first is False:
            for mformat in dict(merged_formats):
                if mformat not in capability['formats']:
                    del merged_formats[mformat]

            # Remove format features not in intersect
            for feature in list(merged_formats[format]['VkFormatProperties']):
                if feature not in capability['formats'][format]['VkFormatProperties']:
                    merged_formats[format]['VkFormatProperties'].remove(feature)

        # Iterate all format features in current json
        if features in capability['formats'][format]['VkFormatProperties']:
            # If mode is union or this is the first json when using intersect add the features if not already in merged features
            if features not in merged_formats[format]['VkFormatProperties']:
                if self.mode == 'union' or self.first == True:
                    merged_formats[format]['VkFormatProperties'][features] = capability['formats'][format]['VkFormatProperties'][features]
            else:
                # In union add all aditional features
                if self.mode == 'union':
                    for feature in capability['formats'][format]['VkFormatProperties'][features]:
                        if feature not in merged_formats[format]['VkFormatProperties'][features]:
                            merged_formats[format]['VkFormatProperties'][features].append(feature)
                # In intersect removed features which are not set in the current json
                else:
                    for feature in list(merged_formats[format]['VkFormatProperties'][features]):
                        if feature not in capability['formats'][format]['VkFormatProperties'][features]:
                            merged_formats[format]['VkFormatProperties'][features].remove(feature)

    def promote_structs(self, promoted, merged, feature):
        for struct in dict(merged):
            if self.get_promoted_struct_name(struct, feature) == promoted and struct is not promoted:
                # Union
                if self.mode == 'union':
                    for member in merged[struct]:
                        merged[promoted][member] = merged[struct][member]
                # Intersect
                elif self.mode == 'intersection':
                    for member in list(merged[promoted]):
                        if member not in merged[struct]:
                            del merged[promoted][member]
                else:
                    print("ERROR: Unknown combination mode: " + self.mode)
                del merged[struct]


    def get_promoted_struct_name(self, struct, feature):
        # Workaround, because Vulkan11 structs were added in vulkan 1.2
        if struct == 'VkPhysicalDeviceVulkan11Features':
            return 'VkPhysicalDeviceVulkan11Features'
        if struct == 'VkPhysicalDeviceVulkan11Properties':
            return 'VkPhysicalDeviceVulkan11Properties'

        version = None
        if self.registry.structs[struct].definedByVersion:
            version = self.registry.structs[struct].definedByVersion
        else:
            aliases = self.registry.structs[struct].aliases
            for alias in aliases:
                if registry.structs[alias].definedByVersion:
                    version = registry.structs[alias].definedByVersion
                    break
        if version is None:
            return False
        return 'VkPhysicalDeviceVulkan' + str(version.major) + str(version.minor) + 'Features' if feature else 'Properties'

    def add_struct(self, struct_name, struct, merged):
        if struct_name in merged:
            # Union
            if self.mode == 'union' or self.first is True:
                for member in struct:
                    merged[struct_name][member] = struct[member]
            # Intersect
            elif self.mode == 'intersection':
                for member in list(merged[struct_name]):
                    if member not in struct:
                        del merged[struct_name][member]
                    elif struct[member] != merged[struct_name][member]:
                        del merged[struct_name][member]
            else:
                print("ERROR: Unknown combination mode: " + self.mode)
        else:
            if self.mode == 'union' or self.first is True:
                merged[struct_name] = struct

    def add_members(self, merged, entry, property = None):
        if self.mode == 'intersection' and self.first is False:
            for member in list(merged):
                if member not in entry:
                    del merged[member]
                #elif entry[member] != merged[member]:
                #    del merged[member]
        for member in entry:
            if property is None or not member in merged:
                if self.mode == 'union' or self.first is True:
                    merged[member] = entry[member]
            else:
                # Merge properties
                xmlmember = self.registry.structs[property].members[member]
                if xmlmember.limittype == 'struct':
                    s = self.registry.structs[self.registry.structs[property].members[member].type].members
                    for smember in s:
                        if smember in merged[member]:
                            if smember in entry[member]:
                                self.merge_members(merged[member], smember, entry[member], s[smember])
                        elif self.mode == 'union' and smember in entry[member]:
                            merged[member][smember] = entry[member][smember]
                else:
                    self.merge_members(merged, member, entry, xmlmember)

    def merge_members(self, merged, member, entry, xmlmember):
        if self.mode == 'union':
            if xmlmember.limittype == 'exact':
                if merged[member] != entry[member]:
                    print("ERROR: values with exact limittype have different values")
            elif 'max' in xmlmember.limittype or xmlmember.limittype == 'bits':
                if xmlmember.arraySize == 3:
                    if entry[member][0] > merged[member][0]:
                        merged[member][0] = entry[member][0]
                    if entry[member][1] > merged[member][1]:
                        merged[member][1] = entry[member][1]
                    if entry[member][2] > merged[member][2]:
                        merged[member][2] = entry[member][2]
                elif xmlmember.arraySize == 2:
                    if entry[member][0] > merged[member][0]:
                        merged[member][0] = entry[member][0]
                    if entry[member][1] > merged[member][1]:
                        merged[member][1] = entry[member][1]
                else:
                    if entry[member] > merged[member]:
                        merged[member] = entry[member]
            elif 'min' in xmlmember.limittype:
                if entry[member] < merged[member]:
                    merged[member] = entry[member]
            elif xmlmember.limittype == 'bitmask':
                for smember in entry[member]:
                    if smember not in merged[member]:
                        merged[member].append(smember)
            elif xmlmember.limittype == 'range':
                if entry[member][0] < merged[member][0]:
                    merged[member][0] = entry[member][0]
                if entry[member][1] > merged[member][1]:
                    merged[member][1] = entry[member][1]
            elif xmlmember.limittype == 'noauto':
                merged.remove(member)
            else:
                print("ERROR: Unknown limitype: " + xmlmember.limittype + " for " + member)
        elif self.mode == 'intersection':
            if xmlmember.limittype == 'exact':
                if merged[member] != entry[member]:
                    print("ERROR: values with exact limittype have different values")
            elif 'max' in xmlmember.limittype or xmlmember.limittype == 'bits':
                if xmlmember.arraySize == 3:
                    if entry[member][0] < merged[member][0]:
                        merged[member][0] = entry[member][0]
                    if entry[member][1] < merged[member][1]:
                        merged[member][1] = entry[member][1]
                    if entry[member][2] < merged[member][2]:
                        merged[member][2] = entry[member][2]
                elif xmlmember.arraySize == 2:
                    if entry[member][0] < merged[member][0]:
                        merged[member][0] = entry[member][0]
                    if entry[member][1] < merged[member][1]:
                        merged[member][1] = entry[member][1]
                else:
                    if entry[member] < merged[member]:
                        merged[member] = entry[member]
            elif 'min' in xmlmember.limittype:
                if entry[member] > merged[member]:
                    merged[member] = entry[member]
            elif xmlmember.limittype == 'bitmask':
                if xmlmember.type == 'VkBool32':
                    if member not in entry:
                        merged.remove(member)
                else:
                    for value in merged[member]:
                        if value not in entry[member]:
                            merged[member].remove(value)
            elif xmlmember.limittype == 'range':
                if entry[member][0] > merged[member][0]:
                    merged[member][0] = entry[member][0]
                if entry[member][1] < merged[member][1]:
                    merged[member][1] = entry[member][1]
                #if member[1] < member[0]:
                #    merged.pop(member, None)
            elif xmlmember.limittype == 'noauto':
                merged.remove(member)
            else:
                print("ERROR: Unknown limitype: " + xmlmember.limittype + " for " + member)
        else:
            print("ERROR: Unknown combination mode: " + self.mode)

    def find_higher_struct(self, struct1, struct2):
        if registry.structs[struct1].definedByVersion:
            return struct1
        if registry.structs[struct2].definedByVersion:
            return struct2
        ext1_ext = False
        ext1_other = False
        ext2_ext = False
        ext2_other = False
        for ext in registry.structs[struct1].definedByExtensions:
            if registry.extensions[ext].name[3:6] == 'EXT':
                ext1_ext = True
            else:
                ext1_other = True
        for ext in registry.structs[struct2].definedByExtensions:
            if registry.extensions[ext].name[3:6] == 'EXT':
                ext2_ext = True
            else:
                ext2_other = True
        
        if not ext1_ext and not ext1_other:
            return struct1
        if not ext2_ext and not ext2_other:
            return struct2
        if not ext1_other:
            return struct1
        if not ext2_other:
            return struct2

        return struct1

    def get_promoted_version(self, vk_version):
        if vk_version is None:
            return None
        version = vk_version[11:]
        underscore = version.find('_')
        major = version[:underscore]
        minor = version[underscore+1:]
        return [major, minor]

    def get_profiles(self, profile_name, api_version, description):
        profiles = dict()
        profiles[profile_name] = dict()
        profiles[profile_name]['version'] = 1
        profiles[profile_name]['status'] = 'BETA'
        profiles[profile_name]['api-version'] = api_version
        profiles[profile_name]['label'] = 'Merged profile'
        profiles[profile_name]['description'] = description
        profiles[profile_name]['contributors'] = dict()
        profiles[profile_name]['history'] = list()
        revision = dict()
        revision['revision'] = 1
        # Get current time
        now = datetime.now()
        revision['date'] = str(now.year) + '-' + str(now.month).zfill(2) + '-' + str(now.day).zfill(2)
        revision['author'] = 'Merge tool'
        revision['comment'] = description
        profiles[profile_name]['history'].append(revision)
        profiles[profile_name]['capabilities'] = list()
        profiles[profile_name]['capabilities'].append('baseline')
        return profiles

    def get_api_version(self, profiles):
        api_version_str = profiles[0]['api-version']
        api_version = self.get_api_version_list(api_version_str)
        for profile in profiles:
            current_api_version_str = profile['api-version']
            current_api_version = self.get_api_version_list(current_api_version_str)
            for i in range(len(api_version)):
                if (api_version[i] > current_api_version[i]):
                    break
                elif (api_version[i] < current_api_version[i]):
                    api_version_str = current_api_version_str
                    api_version = current_api_version
                    break
        return [api_version_str, api_version]

    def get_profile_description(self, profile_names, mode):
        desc = 'Generated profile doing an ' + mode + ' between profiles: '
        count = len(profile_names)
        for i in range(count):
            desc += profile_names[i]
            if i == count - 2:
                desc += ' and '
            elif i < count - 2:
                desc += ', '
        return desc

    def get_version_from_schema(self, schema):
        needle = 'profiles-'
        pos = schema.find(needle) + len(needle)
        ver = schema[pos:]
        version = list()
        version.append(ver[:ver.find('.')])
        ver = ver[ver.find('.') + 1:]
        version.append(ver[:ver.find('.')])
        ver = ver[ver.find('.') + 1:]
        version.append(ver[:ver.find('-')])
        ver = ver[ver.find('-') + 1:]
        version.append(ver[:ver.find('.')])
        return version

    def get_api_version_list(self, ver):
        version = list()
        version.append(ver[:ver.find('.')])
        ver = ver[ver.find('.') + 1:]
        version.append(ver[:ver.find('.')])
        ver = ver[ver.find('.') + 1:]
        version.append(ver[:ver.find('-')])
        ver = ver[ver.find('-') + 1:]
        return version

            

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-registry', action='store',
                        help='Use specified registry file instead of vk.xml')
    parser.add_argument('-profile_dir', action='store',
                        help='Path to directory with profiles')
    parser.add_argument('-profile_path', action='store',
                        help='Path to base profile')
    parser.add_argument('-profile_path2', action='store',
                        help='Path to second profile')
    parser.add_argument('-output_path', action='store',
                        help='Path to output profile')
    parser.add_argument('-profile', action='store',
                        help='Base profile to build the new profile from')
    parser.add_argument('-profile2', action='store',
                        help='Profile to combine into the base profile')
    parser.add_argument('-output_profile', action='store',
                        help='Profile name of the output profile')
    parser.add_argument('-mode', action='store',
                        help='Mode of profile combination')
                        
    args = parser.parse_args()
    if (args.mode is None):
        args.mode = 'union'

    if args.registry is None:
        genvp.Log.e('Merging the profiles requires specifying -registry')
        parser.print_help()
        exit()

    if (args.mode.lower() != 'union' and args.mode.lower() != 'intersection'):
        genvp.Log.e('Mode must be either union or intersection')
        parser.print_help()
        exit()

    if args.output_profile is None:
        args.output_profile = 'VP_LUNARG_merged_' + datetime.now().strftime('%Y_%m_%d_%H_%M')
    elif not re.match('^VP_[A-Z0-9]+[A-Za-z0-9]+', args.output_profile):
        genvp.Log.e('Invalid output_profile, must follow regex pattern ^VP_[A-Z0-9]+[A-Za-z0-9]+')
        exit()

    directory = args.profile_dir is not None
    profile_names = [args.profile, args.profile2]

    # Open file and load json
    jsons = list()
    profiles = list()
    if directory:
        profiles_not_found = profile_names.copy()
        # Find all jsons in the folder
        paths = [args.profile_dir + '/' + pos_json for pos_json in os.listdir(args.profile_dir) if pos_json.endswith('.json')]
        json_files = list()
        for i in range(len(paths)):
            file = open(paths[i], 'r')
            json_files.append(json.load(file))
        # We need to iterate through profile names first, so the indices of jsons and profiles lists will match
        for profile_name in profile_names:
            for json_file in json_files:
                if 'profiles' in json_file and profile_name in json_file['profiles']:
                    jsons.append(json_file)
                    # Select profiles and capabilities
                    profiles.append(json_file['profiles'][profile_name])
                    profiles_not_found.remove(profile_name)
                    break

        if profiles_not_found:
            print('Profiles: ' + ' '.join(profiles_not_found) + ' not found in directory ' + args.profile_dir)
            exit()
    else:
        paths = [args.profile_path, args.profile_path2]
        for i in range(len(paths)):
            file = open(paths[i], 'r')
            jsons.append(json.load(file))
            # Make sure selected profile exists in the file
            if (profile_names[i] not in jsons[i]['profiles']):
                genvp.Log.e('Profile ' + profile_names[i] + ' not found in ' + paths[i])
                exit()
            # Select profiles and capabilities
            profiles.append(jsons[i]['profiles'][profile_names[i]])

    registry = genvp.VulkanRegistry(args.registry)
    profile_merger = ProfileMerger(registry)

    profile_merger.merge(jsons, profiles, profile_names, args.output_path, args.output_profile, args.mode)
    