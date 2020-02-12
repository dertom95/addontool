#! /usr/bin/python3

##
## python-depedencies: Jinja
## (install 'pip install Jinja2') 
##

import json,os,sys,urllib.request
import subprocess
from jinja2 import Environment, PackageLoader, select_autoescape
from pathlib import Path
import argparse

import shutil

home_folder = str(Path.home())

env = Environment(
    loader=PackageLoader('addontool', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

from distutils import spawn 

def error(cause,error_code=1):
    print(cause)
    sys.exit(error_code)

repository_file = "urho3d_repo.json"
root_folder = home_folder+"/.addons"
verbose = True

## todo: use args


git_path = spawn.find_executable("git") 

if not git_path:
    error("git is not found! you need to have git in your path")

def git_clone_or_pull(gitrepo,destination):
    addon_path = destination+"/"+gitrepo.split("/")[-1].replace(".git","")

    if not os.path.exists(addon_path):
        out = subprocess.check_output(["git", "clone",gitrepo],cwd=destination)
        if verbose:
            print("\tgit clone %s : %s" % (gitrepo, out) )
    else:
        out = subprocess.check_output(["git", "pull"],cwd=addon_path)
        if verbose:
            print("\tgit pull %s : %s" % (gitrepo, out) )
    return addon_path

# dict that contains all used gitrepositories and its addons
git_repos = {}
all_addons = {}

def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

class Addon:
    def __init__(self,name,gitrepo):
        self.data = None
        self.name = name
        self.gitrepo = gitrepo

    def get_addon_path(self):
        return self.gitrepo+":"+self.name

    def parse(self,data):
        # todo: do I actually need to set the data in fields?
        self.data = data

    def print_addon(self):
        print("addon: %s" % self.data["name"])

class GitRepo:
    def __init__(self,path):
        self.addons = {}
        self.path = path
        self.local_path = None

    def clone_or_pull(self,root_folder):
        self.local_path = git_clone_or_pull(self.path,root_folder)

    def parse_addons(self,valid_types):
        global all_addons
        addon_file = self.local_path + "/addon.json"
        if not os.path.isfile(addon_file):
            print("%s: no addon-file found" % self.local_path)
            return
        
        with open(addon_file) as json_file:
            data = json.load(json_file)
            
            for addondata in data:
                if addondata["addon_type"] in valid_types:
                    name = addondata["name"]
                    addon = Addon(name,self.path)
                    addon.parse(addondata)
                    addon.data["local_path"] = os.path.abspath(self.local_path)
                    self.addons[name]=addon # gitrepo-addon
                    addonPath = addon.get_addon_path()
                    all_addons[addonPath]=addon # global-addons
                    
                    if verbose:
                        print("Registered: %s" % addonPath)

class AddonGroup:

    def __init__(self,name,data):
        self.addons = {}
        self.name = name
        self.data = data

        for addon in data["addons"]:
            gitrepo = addon["git"]

            if gitrepo not in git_repos:
                git_repos[gitrepo]=GitRepo(gitrepo)

        print("%s : %s" % (self.name,len(self.addons)))

            

    def link_addons(self):
        global all_addons
        print("linked addon %s %s" % (self.data["addons"],len(self.addons)))
        for addon in self.data["addons"]:
            addon_path = "%s:%s" % (addon["git"],addon["addon"])
            if verbose:
                print("addonpath(%s)  :%s" % (self.name,addon_path) )

            if addon_path not in all_addons:
                error("Could not locate addon:%s" % addon_path)

            addon = all_addons[addon_path]
            self.addons[addon.name] = addon 
            
            if verbose:
                print("linked addon %s %s" % (addon_path,len(self.addons)))

    def to_json(self):
        json_output = {}
        json_output["addongroup_name"]=self.name
        json_addons = []
        for addon in self.addons.values():
            print("%s:%s" % (self.name,addon.name))
            json_addons.append(addon.data)
        json_output["addons"]=json_addons
        return json_output
    

    def print_group(self):
        print("\t\taddons: %s" % ",".join(self.addons.keys()))
        print("\t\tgit-repos:%s\n" % ("\n\t".join(git_repos.keys()) ))            


class RepoDescription:
    def __init__(self,jsondata):
        self.addon_groups = {}
        self.default_addon_group = None
        self.data = jsondata
        self.name = jsondata["repo_name"]
            
        # addon groups
        for addon_group_name in jsondata["addon_groups"]:
            print("create addongroup:",addon_group_name)
            addon_group = AddonGroup(addon_group_name,jsondata["addon_groups"][addon_group_name])
            self.addon_groups[addon_group_name] = addon_group

        if "default_addon_group" in jsondata:
            default_addon_group = jsondata["default_addon_group"]

            if default_addon_group not in self.addon_groups:
                error("Unknown default repo:%s" % default_addon_group)
            
            self.default_addon_group = self.addon_groups[default_addon_group]
        else:
            if len(self.addon_groups) > 0:
                self.default_addon_group = self.addon_groups[0]

    def clone_or_pull(self,root_folder):
        for git_repo in git_repos:
            git_repos[git_repo].clone_or_pull(root_folder)

    def scan_for_addons(self):
        for git_repo in git_repos:
            git_repos[git_repo].parse_addons(self.data["valid_addon_types"])
        
        for addon_group in self.addon_groups.values():
            addon_group.link_addons()


    def get_addon_group(self,addon_group_name=None):
        if not addon_group_name:
            return self.default_addon_group
        
        try:
            return self.addon_groups[addon_group_name]
        except:
            return None

    def print_repo(self):
        print("addon repository %s\n" % self.name)
        print("valid-addon-type: %s" % ( ",".join(self.data["valid_addon_types"]) ))
        print("addon-groups:")
        for addon_grp in self.addon_groups:
            print("\t%s : " % addon_grp)
            self.addon_groups[addon_grp].print_group()

    def write_repo_to_jsonfile(self,filepath):
        json_output = {}
        json_output["repo_name"] = self.data["repo_name"]
        json_output["repo_description"] = self.data
        json_output["default_group"]=self.default_addon_group.name
        json_addon_groups = {}
        for addon_group in self.addon_groups.values():
            json_addon_groups[addon_group.name] = addon_group.to_json()

        json_output["addon_groups"]=json_addon_groups
        
        with open(filepath, 'w') as outfile:
            json.dump(json_output, outfile, indent=4)

        print("ok.")        

def parse_repo_description_file(repo_file):
    if not os.path.isfile(repo_file):
        error("Could not access repo-description-file:%s" % (repo_file))

    with open(repo_file) as json_file:
        data = json.load(json_file)
        repo_desc = RepoDescription(data)
        return repo_desc

    return None

def parse_repo_file(repo_file):
    if not os.path.isfile(repo_file):
        error("Could not access repo-file:%s" % (repo_file))

    with open(repo_file) as json_file:
        data = json.load(json_file)
        print ("REPONAME:%s" % data["repo_name"])
        return data
        
    return None

def parse_addons_installed(file):
    if not os.path.isfile(file):
        new_addons_list = {}
        return new_addons_list

    with open(file) as json_file:
        data = json.load(json_file)
        return data
    return None

def loadRepoDescription(repo_descr_file):
    if not os.path.isdir(root_folder):
        os.makedirs(root_folder)

    repoDescr = parse_repo_description_file(repo_descr_file) 
    return repoDescr

def processRepoDescription(repoDescr):
    if repoDescr:
        repoDescr.print_repo()
        repoDescr.clone_or_pull(root_folder)
        repoDescr.scan_for_addons()
        repoDescr.write_repo_to_jsonfile(root_folder+"/addon_repo.json")
        outputHTML(root_folder+"/addon_repo.json")

def processRepo(repo_file=None):
    if not repo_file:
        repo_file = root_folder+"/addon_repo.json"

    return parse_repo_file(repo_file)

def outputHTML(repo_file=None):
    repo = processRepo(repo_file)

    template = env.get_template('repo_template.html')
    file = open(root_folder+"/addon_repo.html","w") 
    file.write(template.render(data=repo))
    file.close()

def show_addons(addon_group=None,repo_file=None):
    repo = processRepo(repo_file)

    addon_group = addon_group or repo["default_group"]

    print("\naddon-group: %s" % addon_group)
    if addon_group in repo["addon_groups"]:
        for addon in repo["addon_groups"][addon_group]["addons"]:
            print("\t%s (%s - %s)" % (addon["name"].ljust(20," "),addon["category"],addon["description"])  )
    else:
        print("error! unknown addon_group %s" % addon_group)

def print_help():
        print("addontool by Thomas Trocha (dertom)")
        print("\t --create-repo [description.json]")
        print("\t --create-html-from-repo [repo.json]")
        print("\t --addons [addon_group]")
        print()

# repository_file = "urho3d_repo.json"
# root_folder = home_folder+"/.addons"
# verbose = True

def list_addon_groups():
    repo = processRepo()

    print("addon-groups:")
    for addon_grp_name in repo["addon_groups"]:
        isdefault=" (default)" if repo["default_group"]==addon_grp_name else ""
        print("\n\t%s%s:" % (addon_grp_name,isdefault))
        addon_grp = repo["addon_groups"][addon_grp_name]
        if len(addon_grp["addons"]):
            for addon in addon_grp["addons"]:
                print("\t\t%s - %s - %s" % (addon["name"].ljust(15),addon["description"].ljust(50),addon["category"]))
        else:
            print("\t\tno addons")

    print()

def copy_folders(base,from_list,destination):
    try:
        for folder in from_list:
            destpath = destination+"/"+folder

            if not os.path.exists(destpath):
                os.makedirs(destpath)

            copytree(base+"/"+folder, destpath)

    except Exception as e:
        print(e)
        print("no folders")

def copy_file(base,file,destination):
    try:
        fullpath = base+"/"+file
        out = destination+"/"+file

        dirname = os.path.dirname(out)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        print("copy file %s => %s" % ( fullpath,out ))
        shutil.copy2(fullpath,out)
    except Exception as e:
        print(e)


def install(addonname,outputfolder):
    repo = processRepo()
    addons_installed_path=outputfolder+"/.addons_installed.json"
    addons_installed = parse_addons_installed(addons_installed_path)

    splits = addonname.split('/')
    addon_group = None
    if len(splits)==2:
        addon_group = splits[0]
        addonname = splits[1]

    if addon_group:
        try:
            addon_group = repo["addon_groups"][addon_group]            
        except:
            error("unknown addon_group:%s" % addon_group)
        
    else:
        addon_group = repo["addon_groups"][repo["default_group"]]
    
    for addon in addon_group["addons"]:
        if addon["name"] == addonname:
            print(addon)
            copy_folders(addon["local_path"],addon["files"]["folders"],outputfolder)
            print("installed %s" % addon["name"])
            
            for filename in addon["files"]["files"]:
                try:
                    copy_file(addon["local_path"],filename,outputfolder)
                except Exception as e:
                    print(e)

            if addonname not in addons_installed:
                addons_installed[addonname]=addon

            with open(addons_installed_path, 'w') as outfile:
                json.dump(addons_installed, outfile, indent=4)
    
    
    template = env.get_template('Addons.template.cmake')
    file = open(outputfolder+"/CMake/IncludeAddons.cmake","w") 
    file.write(template.render(data=addons_installed))
    file.close()

    

def main():
    global root_folder,verbose

    dirpath = os.getcwd()

    parser = argparse.ArgumentParser(description="addontool by Thomas Trocha")
    parser.add_argument("--repo_folder",help="custom output folder. (default: %s)" % root_folder)
    parser.add_argument("--init",help="create repository file from repo-description")
    parser.add_argument("--update",action="store_true",help="updates the current repo")
    parser.add_argument("--install",help="install addon. specify addonname (optionally prefix addon-group with '/'-separator)")
    parser.add_argument("--install_output",default=dirpath,help="custom install output. as default the current folder (%s)" % dirpath)
    parser.add_argument("--verbose",action='store_true',help="output some internal logs")
    parser.add_argument("--list_addon_groups",action="store_true",help="show all addon-groups for the current repo")
    parser.add_argument("--addon_group",help="select specfifc addon-group")
    

    if len(sys.argv)==1:
        print("1")
        args = parser.parse_args(['--help'])
    else:
        print("2")
        args = parser.parse_args()

        verbose = args.verbose

        if args.repo_folder:
            root_folder = args.repo_folder

        if args.init:
            repo_descr = loadRepoDescription(args.init)
            processRepoDescription(repo_descr)

        if args.update:
            repo = processRepo()
            repo_desc = RepoDescription(repo["repo_description"])
            processRepoDescription(repo_desc)
            print("updated")

        if args.install:
            install(args.install,args.install_output)

        if args.list_addon_groups:
            list_addon_groups()

    print(args)
    # arg_count = len(sys.argv)
    # if arg_count==1:
    #     print_help();
    # else:
    #     cmd = sys.argv[1]
    #     if cmd =="--create-repo":
    #         if arg_count < 3:
    #             print("--create-repo : you need to specify a description-file")
    #             print_help()
    #             sys.exit(1)
    #     elif cmd == "--create-html-from-repo"
    #     processRepoDescription(repository_file)

    #     #outputHTML()

    #     show_addons()

if __name__ == "__main__":
    main()        
