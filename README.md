<!-- markdownlint-disable MD041 -->
<p align="left"><img src="https://vulkan.lunarg.com/img/NewLunarGLogoBlack.png" alt="LunarG" width=263 height=113 /></p>
<p align="left">Copyright © 2021-2022 LunarG, Inc.</p>

<p align="center"><img src="./images/logo.png" width=400 /></p>

[![Creative Commons][3]][4]

[3]: https://i.creativecommons.org/l/by-nd/4.0/88x31.png "Creative Commons License"
[4]: https://creativecommons.org/licenses/by-nd/4.0/

The *Vulkan Profiles Tools* are a collection of tools for Vulkan application developers to leverage *Vulkan Profiles* while developing a Vulkan application.

* **[Change Log](./CHANGELOG.md)**: The history of *Vulkan Profiles Tools* releases.
* **[Bug reports](https://github.com/LunarG/VulkanProfiles/issues)**: Open a GitHub issue when you encounter a bug.
* **[Roadmap](https://github.com/LunarG/VulkanProfiles/projects)**: Follow *Vulkan Profiles Tools* future developments.
* **[Contributing](./PROFILES.md)**: The definitions of *Vulkan Profiles*.
* **[Contributing](./TUTORIAL.md)**: How to use the *Vulkan Profiles Tools*.

--------------
### The Vulkan Profiles Schema

The *[Vulkan Profile Schema](./schema/profiles.json)* aims at providing a human readable format to store and share data representing properties, features, extensions, formats, etc.

It can be used to represent Vulkan capabilities for many differents usages::
- Roadmap profiles: To give a perspective of where the Khronos members are converging
- Platform profiles: To express the Vulkan support of a platform 
- Device profiles: To express the Vulkan support of a device, generated by GPUInfo.org at Vulkan 1.3 SDK release and vulkaninfo in the future.
- Engine profiles: To express some rendering code paths requirements of an engine
- Etc.

--------------
### The Vulkan Profiles Registry

This repository contains representation of profiles following the *Vulkan Profile Schema*:
- [VP_KHR_roadmap_2022](./profiles/VP_KHR_roadmap_2022.json)
- [VP_LUNARG_desktop_portability_2021](./profiles/VP_LUNARG_desktop_portability_2021.json)
- [VP_ANDROID_angle_es31](./profiles/VP_ANDROID_angle_es31.json)
- [VP_ANDROID_baseline_2022](./profiles/VP_ANDROID_baseline_2022.json)

--------------
## The Vulkan Profiles Library: vulkan_profiles.hpp

The *Vulkan Profiles Library* provides an API to leverage *Vulkan Profiles* in Vulkan applications code with the following features:
- Checking whether specific *Vulkan Profiles* are supported
- Creating `VkDevice` instances with the features of a *Vulkan Profile* enabled
- Reflecting on *Vulkan Profiles* features

When using the Vulkan SDK, to use the library simply include <vulkan/vulkan_profiles.hpp>.

This library is available in two forms. It can either be a header-only library or a source and header library that can simply be copy pasted to the engine code.

This library is hand-written for the initial release but we are planning to generate it from JSON profile files using a python script so that any Vulkan developer could create a profile and directly use it in C++ code.

--------------
### Platforms Support

| Windows            | Linux               | macOS              | iOS                | Android            |
| ------------------ | ------------------- | ------------------ | ------------------ | ------------------ |
| :heavy_check_mark: | :heavy_check_mark:  | :heavy_check_mark: | :x:                | :heavy_check_mark: |

--------------
## The Vulkan Profiles Layer: VK_LAYER_KHRONOS_device_simulation

The validation layer assists developers in checking their code for improper use of Vulkan, but these checks take into account only the capabilities of the test platform. To ensure an application properly handles multiple platforms, these checks must be run on all platforms of interest to the Vulkan developer. Combinations of GPUs, ICDs, drivers, and operating systems to name a few factors create an exponential number of possible test platforms, which is infeasible for a developer to obtain and maintain.

The *Device Simulation Layer* seeks to mitigate this obstacle by providing a method to simulate arbitrary Vulkan capabilities from the actual device capabilities to run specific test cases. The layer can be configured using a profile to ensure the application is never using more features than expected, preventing it from not running on expected supported platforms.
--------------
### Platforms Support

| Windows            | Linux               | macOS              | iOS                | Android            |
| ------------------ | ------------------- | ------------------ | ------------------ | ------------------ |
| :heavy_check_mark: | :heavy_check_mark:  | :heavy_check_mark: | :x:                | :heavy_check_mark: |

--------------
## Downloads

*Vulkan Profiles Tools* is delivered with the [Vulkan SDK](https://vulkan.lunarg.com/sdk/home).


