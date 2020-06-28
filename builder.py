# This is small 'build system' that i use to build Typerminal itself and my second personal project.


import sys
import os
import ascii_colors
import subprocess
import types
import threading
import time
from pathlib import Path

class Build_Options:
	def __init__(self):
		self.disable_warnings = False
		self.generate_debug_symbols = True

		self.optimization_level = 0

		self.src_directory = None
		self.output_directory = None

		self.architecture = None
		self.vendor = None
		self.system = None
		self.abi = None

		self.executable_path = None

		self.sources = None

		self.include_directories = []

		self.lib_directories = []

		self.defines = []

		self.root_dir = None
		self.intermidiate_dir = None

		self.use_clang_cl = False

		self.use_windows_dynamic_crt = False
		self.use_windows_crt_debug_version = False
		self.use_windows_subsystem = False

		self.avx = False

		self.output_assembly = False




root_dir = ''
intermidiate_dir = ''
src_dir = ''


def build(build_options):

	global root_dir
	global intermidiate_dir
	global src_dir

	root_dir = build_options.root_dir
	intermidiate_dir = os.path.join(root_dir, build_options.intermidiate_dir)
	src_dir = os.path.join(root_dir,  build_options.src_directory)


	os.makedirs(intermidiate_dir, exist_ok = True)


	any_failed_source = False

	threads = []

	for source in build_options.sources:

		cmd_line = build_clang_command_line_for_source(build_options, source)

		print_result_lock = threading.Lock()

		def build_thread_proc(source):
			run_result = subprocess.run(cmd_line, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, stdin = subprocess.DEVNULL)
			
			print_result_lock.acquire()

			succeeded = run_result.returncode == 0

			nonlocal any_failed_source

			if not succeeded:
				any_failed_source = True
		

			file_name_background_rgb = (20, 150, 0) if succeeded else (200, 20, 0)


			file_name_to_print = source
			if not succeeded:
				file_name_to_print += " (FAILED) "
			else:
				file_name_to_print += " (SUCCEEDED) "
				
				if build_options.output_assembly:
					file_name_background_rgb = (0, 150, 150)
					file_name_to_print += f' -> {get_asm_output_path(source)}  '





			print(f'{ascii_colors.rgb(*file_name_background_rgb).background}{ascii_colors.rgb(0, 0, 0).foreground}--- {file_name_to_print}{ascii_colors.reset_background_color}{ascii_colors.reset_foreground_color}')

			if len(run_result.stdout):
				sys.stdout.write('\n')
				print(run_result.stdout.decode('utf-8'))
				print('\n\n')


			print_result_lock.release()


		build_thread = threading.Thread(target = build_thread_proc, args = [source])
		build_thread.start()

		threads.append(build_thread)


	for thread in threads:
		thread.join()

	if any_failed_source or build_options.output_assembly:
		return



	run_result = subprocess.run(build_linker_command_line(build_options), stdout = subprocess.PIPE, stderr = subprocess.STDOUT, stdin = subprocess.DEVNULL)
	succeeded = run_result.returncode == 0

	linking_result_title_background = (20, 150, 0) if succeeded else (200, 20, 0)
	linking_result_title = "LINKING "
	if not succeeded:
		linking_result_title += " FAILED "
	else:
		linking_result_title += " SUCCEEDED "

	print(f'{ascii_colors.rgb(*linking_result_title_background).background}{ascii_colors.rgb(0, 0, 0).foreground}--- {linking_result_title}{ascii_colors.reset_background_color}{ascii_colors.reset_foreground_color}')

	print(run_result.stdout.decode('utf-8', errors = 'ignore'))

	if succeeded:
		print(f'{ascii_colors.yellow}{get_linker_output_path(build_options)}{ascii_colors.reset_foreground_color}\n')


def get_asm_output_path(source):
	return os.path.join(intermidiate_dir, f"{Path(source).stem}.asm")

def get_source_output_path(source):
	return os.path.join(intermidiate_dir, f"{Path(source).stem}.obj")

def get_linker_output_path(build_options):
	return os.path.normpath(os.path.join(root_dir, f"{build_options.executable_path}"))


def build_linker_command_line(build_options):
	linker_inputs = ' '
	for source in build_options.sources:
		linker_inputs += ' "'
		linker_inputs += get_source_output_path(source)
		linker_inputs += '" '


	cmd = 'clang-cl' if build_options.use_clang_cl else 'clang++'

	cmd += f' {linker_inputs} '

	cmd += ' -fuse-ld=lld-link '


	if build_options.use_clang_cl:
		cmd += f' {get_windows_crt_variant(build_options)} '

	if build_options.use_clang_cl:
		cmd += ' /clang:-g '
	else:
		cmd += ' -g '

	
	linker_output_path = get_linker_output_path(build_options)

	if build_options.use_clang_cl:
		cmd += f' /clang:--output="{linker_output_path}"'
	else:
		cmd += f' --output="{linker_output_path}"'


	#cmd += f' -v '


	for lib_dir in build_options.lib_directories:
		lib_path = os.path.join(root_dir, lib_dir)
		
		if build_options.use_clang_cl:
			cmd += f' -clang:--for-linker=/LIBPATH:"{lib_path}" '
		else:
			cmd += f' --library-directory="{lib_path}" '


	if build_options.use_clang_cl and build_options.use_windows_subsystem:
		cmd += ' -clang:--for-linker=/SUBSYSTEM:WINDOWS ' 
		cmd += ' -clang:--for-linker=/entry:mainCRTStartup '

	return cmd


def get_windows_crt_variant(build_options):
	assert(build_options.use_clang_cl)

	if build_options.use_windows_dynamic_crt:
		if build_options.use_windows_crt_debug_version:
			return '/MDd'
		else:
			return '/MD'
	else:
		if build_options.use_windows_crt_debug_version:
			return '/MTd'
		else:
			return '/MT'


def build_clang_command_line_for_source(build_options, source):


	cmd = 'clang-cl' if build_options.use_clang_cl else 'clang++'
	

	if build_options.disable_warnings:
		cmd += ' -Wno-everything '


	def add_flag(flag):
		nonlocal cmd
		cmd += ' '
		cmd += flag
		cmd += ' '


	if build_options.use_clang_cl:
		cmd += '  /TP ' # Compile as C++
		cmd += f' {get_windows_crt_variant(build_options)} '



	# Typerminal doesn't support support Windows Console API coloring stuff. 
	add_flag('-fansi-escape-codes')
	# We always want our output to be colored
	add_flag('-fcolor-diagnostics')

	if build_options.use_clang_cl:
		add_flag('/std:c++latest')
	else:
		add_flag('-std=c++2a')


	if build_options.output_assembly:
		if build_options.use_clang_cl:
			add_flag('/c')  
			add_flag(f'/Fa"{get_asm_output_path(source)}"')  
		else:
			raise Exception("I couldn't make clang++ output assembly, please set build_options.use_clang_cl = True for now it will do that ")
			add_flag(f'-S --output="{get_asm_output_path(source)}"')  
	else:	
		# Prevent linker execution
		if build_options.use_clang_cl:
			add_flag('/c')  
		else:
			add_flag('-c')




	if not build_options.use_clang_cl:
		target_name = f'{build_options.architecture}-{build_options.vendor}-{build_options.system}-{build_options.abi}'
		add_flag(f'--target={target_name}')


	if build_options.generate_debug_symbols:
		if build_options.use_clang_cl:
			add_flag('/Zi')
		else:
			add_flag('-gcodeview')
			add_flag('-g')

	for inc in build_options.include_directories:
		inc_path = os.path.join(src_dir, inc)
		
		if build_options.use_clang_cl:
			add_flag(f'/I"{inc_path}"')
		else:
			add_flag(f'--include-directory="{inc_path}"')



	if build_options.avx:
		if build_options.use_clang_cl:
			add_flag(f'/arch:AVX')
		else:
			add_flag(f'-mavx')



	for define in build_options.defines:
		if isinstance(define, tuple):
			if build_options.use_clang_cl:
				add_flag(f'/D{define[0]}={define[1]}')
			else:
				add_flag(f'-D{define[0]}={define[1]}')
		else:
			if build_options.use_clang_cl:
				add_flag(f'/D{define}')
			else:
				add_flag(f'-D{define}')



	if not (build_options.optimization_level >= 0 and build_options.optimization_level <= 3):
		raise Exception('optimization_level should be integer in range[0; 3]')


	if build_options.use_clang_cl:
		if build_options.optimization_level == 0:
			add_flag('/Od')
		elif build_options.optimization_level == 1:
			add_flag('/O2')
		elif build_options.optimization_level == 2:
			add_flag('/O2')
		elif build_options.optimization_level == 3:
			add_flag('/O2ix')

	else:
		if build_options.optimization_level == 0:
			add_flag('-O0')
		elif build_options.optimization_level == 1:
			add_flag('-O1')
		elif build_options.optimization_level == 2:
			add_flag('-O2')
		elif build_options.optimization_level == 3:
			add_flag('-O3')



	if not build_options.output_assembly:
		if build_options.use_clang_cl:
			cmd += f' /Fo"{get_source_output_path(source)}"'
		else:
			cmd += f' --output="{get_source_output_path(source)}"'

	cmd += ' "'
	cmd += os.path.join(src_dir, source)
	cmd += '" '


	#print(cmd)

	return cmd

