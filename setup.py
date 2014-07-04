from setuptools import setup
try:
    import py2exe
except:
    print "No py2exe here"
 

 
 

setup(
    name="SAXS",
    version="0",
    packages=["SAXS"],
    package_data={"SAXS": ["schema.json"]},
    author="Christian Meisenbichler",
    author_email="chmberg@gmail.com",
    description="Tools for analysing SAXS Data",
    requires=["numpy","scipy", "matplotlib","jsonschema", "bitarray"," watchdog"," sphinxcontrib.programoutput"],
    license="Proprietary",
    entry_points = {
        'console_scripts': [
            'saxsconverter = SAXS:convert',
            'saxsdog = SAXS:saxsdog',
            'plotchi=SAXS:plotchi']
        
    }
)
 