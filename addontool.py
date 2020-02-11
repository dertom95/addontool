##
## python-depedencies: Jinja
## (install 'pip install Jinja2') 
##

import json,os,sys,urllib.request
import subprocess
from jinja2 import Environment, PackageLoader, select_autoescape
from pathlib import Path
import argparse

home_folder = str(Path.home())

env = Environment(
    loader=PackageLoader('addontool', 'html'),
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
    addon_path = destination+"/"+gitrepo.split("/")[-1]

    if not os.path.exists(addon_path):
        out = subprocess.check_output(["git", "clone",gitrepo],cwd=destination)
        if verbose:
            print("\tgit clone %s : %s" % (gitrepo, out) )
    else:
        out = subprocess.check_output(["git", "pull"],cwd=addon_path)
        if verbose:
            print("\tgit pull %s : %s" % (gitrepo, out) )

# dict that contains all used gitrepositories and its addons
git_repos = {}
all_addons = {}

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

    def clone_or_pull(self,root_folder):
        git_clone_or_pull(self.path,root_folder)

    def parse_addons(self,valid_types):
        global all_addons
        addon_file = self.path + "/addon.json"
        if not os.path.isfile(addon_file):
            print("%s: no addon-file found" % self.path)
            return
        
        with open(addon_file) as json_file:
            data = json.load(json_file)
            
            for addondata in data:
                if addondata["addon_type"] in valid_types:
                    name = addondata["name"]
                    addon = Addon(name,self.path)
                    addon.parse(addondata)
                    addon.data["local_path"] = self.path
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
            gitrepo,_ = addon.split(':')

            if gitrepo not in git_repos:
                git_repos[gitrepo]=GitRepo(gitrepo)

        print("%s : %s" % (self.name,len(self.addons)))

            

    def link_addons(self):
        global all_addons
        print("linked addon %s %s" % (self.data["addons"],len(self.addons)))
        for addon_path in self.data["addons"]:
            if verbose:
                print("addonpath(%s)  :%s" % (self.name,addon_path) )

            if addon_path not in all_addons:
                error("Could not locate addon:%s" % addon_path)

            addon = all_addons[addon_path]
            self.addons[addon.name] = addon 
            
            if verbose:
                print("linked addon %s %s" % (addon_path,len(self.addons)))

    def export_files(self,output_folder):
        pass    

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
            json.dump(json_output, outfile,sort_keys=True, indent=4)

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

def main():
    global root_folder,verbose

    parser = argparse.ArgumentParser(description="addontool by Thomas Trocha")
    parser.add_argument("--init",help="create repository file from repo-description")
    parser.add_argument("--update",action="store_true",help="updates the current repo")
    parser.add_argument("--repo_folder",help="custom output folder. (default: %s)" % root_folder)
    parser.add_argument("--verbose",action='store_true',help="output some internal logs")
    
    if len(sys.argv)==1:
        args = parser.parse_args(['--help'])
        sys.exit(1)
    else:
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
