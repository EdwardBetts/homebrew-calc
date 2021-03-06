#!/usr/bin/python

import json
import argparse
import sys
from units import units

def execute(config, recipe_config):
    if 'Mash' not in recipe_config or 'type' not in recipe_config['Mash']:
        print 'Mash information not provided'
        sys.exit()

    if recipe_config['Mash']['type'] == 'Infusion':
        config, recipe_config = infusion_mash(config, recipe_config)
    elif recipe_config['Mash']['type'] == 'Step':
        config, recipe_config = step_mash(config, recipe_config)
    else:
        print 'Not supported.'
        sys.exit()

    if 'Output' in config:
        with open(config['Output'], 'w') as outfile:
            json.dump(recipe_config, outfile, indent=2, sort_keys=True)

def step_mash(config, recipe_config):
    """ Mash with multiple steps. """

    if 'steps' not in recipe_config['Mash']:
        print 'Steps not specified; exiting.'
        sys.exit()

    steps = recipe_config['Mash']['steps']

    for step in steps:
        if 'temperature' not in step or 'duration' not in step:
            print 'Must specify temperature and duration for each step.'
            sys.exit()

    first_step = steps[0]
    mash_temp = fahrenheit_to_celsius(first_step['temperature'])
    mash_duration = config['unit'].convertUnits(first_step['duration'], 'hours')

    ambient_temp, mwv, gtm, water_density, water_specific_heat, mttm, hlttm, hldt, hlit, mcr, sparge_temp, boiling_temp = get_common_params(config, recipe_config)

    mwtm = mwv * water_density * water_specific_heat # calories per degC

    if 'Water Temperature in Kettle' in first_step:
        wtika = fahrenheit_to_celsius(first_step['Water Temperature in Kettle'])
    else:
        wtika = None

    if 'Water Temperature in Mashtun' in first_step:
        wtitaa = fahrenheit_to_celsius(first_step['Water Temperature in Mashtun'])
    else:
        wtitaa = None
    
    if 'Final Mash Temperature' in first_step:
        mtfa = fahrenheit_to_celsius(first_step['Final Mash Temperature'])
    else:
        mtfa = None

    # Water temp in kettle
    wtik = mash_temp * (mwtm + mttm + gtm) - ambient_temp * (gtm + mttm) + hlit * (mttm + mwtm)
    wtik /= mwtm
    wtik += hldt

    if wtika is None:
        wtit = (mwtm * (wtik - hldt) + ambient_temp * mttm) / (mttm + mwtm)
    else:
        wtit = (mwtm * (wtika - hldt) + ambient_temp * mttm) / (mttm + mwtm)
        
    wtita = (mash_temp * (mttm + mwtm + gtm) - ambient_temp * gtm) / (mttm + mwtm)

    if wtitaa is None:
        wtitwg = (wtita * (mttm + mwtm) + ambient_temp * gtm) / (mttm + mwtm + gtm)
    else:
        wtitwg = (wtitaa * (mttm + mwtm) + ambient_temp * gtm) / (mttm + mwtm + gtm)
        
    mtf = wtitwg - mcr * mash_duration

    print 'Heat mash water ({0:.2f} gallons) to {1:.1f} degF.'.format(config['unit'].convertUnits(mwv, 'liters', 'gallons'), celsius_to_fahrenheit(wtik))
    if wtika is not None:
        print 'Actual temperature achieved: {0:.1f} degF.'.format(celsius_to_fahrenheit(wtika))
    
    print 'After adding to mash tun (before adding grain), temperature is predicted to be {0:.1f} degF.'.format(celsius_to_fahrenheit(wtit))
    print 'Allow water to cool to {0:.1f} degF before adding grain.'.format(celsius_to_fahrenheit(wtita))
    if wtitaa is not None:
        print 'Actual temperature: {0:.1f} degF.'.format(celsius_to_fahrenheit(wtitaa))
        
    print 'After adding grain and stirring, temperature is predicted to be {0:.1f} degF.'.format(celsius_to_fahrenheit(wtitwg))

    print 'After {0:.0f} minutes, mash temp is expected to decrease to {1:.1f} degF.'.format(config['unit'].convertUnits(mash_duration, 'hours', 'minutes'), celsius_to_fahrenheit(mtf))
    if mtfa is not None:
        print 'Actual temperature: {0:.1f} degF.'.format(celsius_to_fahrenheit(mtfa))
    else:
        mtfa = mtf


    # Combined thermal mass
    ctm = mttm + mwtm + gtm

    for step in steps[1:]:
        step_temp = fahrenheit_to_celsius(step['temperature'])
        step_duration = config['unit'].convertUnits(step['duration'], 'hours')
        # mash_temp * (swtm + ctm) = bt * swtm + mtfa * ctm
        # mash_temp * swtm + mash_temp * ctm = bt * swtm + mtfa * ctm
        # mash_temp * ctm - mtfa * ctm = bt * swtm - mash_temp * swtm
        # (mash_temp - mtfa) * ctm = (bt - mash_temp) * swtm
        swtm = ctm * (step_temp - mtfa) / (boiling_temp - step_temp)
        swv = swtm / (water_specific_heat * water_density)
        ctm += swtm

        print 'To bring mash up to {0:.1f} degF, add {1:.1f} gallons boiling water.'.format(celsius_to_fahrenheit(step_temp), config['unit'].convertUnits(swv, 'liters', 'gallons'))

        if 'Achieved Mash Temperature' in step:
            print 'Temperature achieved: {0:.1f} degF'.format(step['Achieved Mash Temperature'])
            step_temp = fahrenheit_to_celsius(step['Achieved Mash Temperature'])

        mtf = step_temp - mcr * step_duration
        
        print 'After {0:.0f} minutes, temperature is predicted to drop to {1:.1f} degF.'.format(config['unit'].convertUnits(step_duration, 'hours', 'minutes'), celsius_to_fahrenheit(mtf))

        if 'Final Mash Temperature' in step:
            print 'Actual temperature: {0:.1f} degF'.format(step['Final Mash Temperature'])
            mtfa = fahrenheit_to_celsius(step['Final Mash Temperature'])
        else:
            mtfa = mtf
        
    swtm = ctm * (sparge_temp - mtfa) / (boiling_temp - sparge_temp)
    swv = swtm / (water_specific_heat * water_density)

    print 'To mash out at {0:.1f} degF, add {1:.1f} gallons boiling water.'.format(celsius_to_fahrenheit(sparge_temp), config['unit'].convertUnits(swv, 'liters', 'gallons'))
    
    return config, recipe_config

def infusion_mash(config, recipe_config):
    """ Simple infusion mash. """
    
    if 'temperature' in recipe_config['Mash']:
        mash_temp = fahrenheit_to_celsius(recipe_config['Mash']['temperature'])
    else:
        print 'Mash temperature not specified.'
        sys.exit()

    if 'duration' in recipe_config['Mash']:
        mash_duration = config['unit'].convertUnits(recipe_config['Mash']['duration'], 'hours')
    else:
        mash_duration = 1
        print 'Mash duration not specified, assuming {0:.1f} hours.'.format(mash_duration)

    ambient_temp, mwv, gtm, water_density, water_specific_heat, mttm, hlttm, hldt, hlit, mcr, sparge_temp, boiling_temp = get_common_params(config, recipe_config)
    
    mwtm = mwv * water_density * water_specific_heat # calories per degC

    if 'Water Temperature in Kettle' in recipe_config:
        wtika = fahrenheit_to_celsius(recipe_config['Water Temperature in Kettle'])
    else:
        wtika = None

    if 'Water Temperature in Mashtun' in recipe_config:
        wtitaa = fahrenheit_to_celsius(recipe_config['Water Temperature in Mashtun'])
    else:
        wtitaa = None
    
    if 'Final Mash Temperature' in recipe_config:
        mtfa = fahrenheit_to_celsius(recipe_config['Final Mash Temperature'])
    else:
        mtfa = None

    # Water temp in kettle
    wtik = mash_temp * (mwtm + mttm + gtm) - ambient_temp * (gtm + mttm) + hlit * (mttm + mwtm)
    wtik /= mwtm
    wtik += hldt

    if wtika is None:
        wtit = (mwtm * (wtik - hldt) + ambient_temp * mttm) / (mttm + mwtm)
    else:
        wtit = (mwtm * (wtika - hldt) + ambient_temp * mttm) / (mttm + mwtm)
        
    wtita = (mash_temp * (mttm + mwtm + gtm) - ambient_temp * gtm) / (mttm + mwtm)

    if wtitaa is None:
        wtitwg = (wtita * (mttm + mwtm) + ambient_temp * gtm) / (mttm + mwtm + gtm)
    else:
        wtitwg = (wtitaa * (mttm + mwtm) + ambient_temp * gtm) / (mttm + mwtm + gtm)
        
    mtf = wtitwg - mcr * mash_duration


    print 'Heat mash water ({0:.2f} gallons) to {1:.1f} degF.'.format(config['unit'].convertUnits(mwv, 'liters', 'gallons'), celsius_to_fahrenheit(wtik))
    if wtika is not None:
        print 'Actual temperature achieved: {0:.1f} degF.'.format(celsius_to_fahrenheit(wtika))
    
    print 'After adding to mash tun (before adding grain), temperature is predicted to be {0:.1f} degF.'.format(celsius_to_fahrenheit(wtit))
    print 'Allow water to cool to {0:.1f} degF before adding grain.'.format(celsius_to_fahrenheit(wtita))
    if wtitaa is not None:
        print 'Actual temperature: {0:.1f} degF.'.format(celsius_to_fahrenheit(wtitaa))
        
    print 'After adding grain and stirring, temperature is predicted to be {0:.1f} degF.'.format(celsius_to_fahrenheit(wtitwg))

    print 'After {0:.0f} minutes, mash temp is expected to decrease to {1:.1f} degF.'.format(config['unit'].convertUnits(mash_duration, 'hours', 'minutes'), celsius_to_fahrenheit(mtf))
    if mtfa is not None:
        print 'Actual temperature: {0:.1f} degF.'.format(celsius_to_fahrenheit(mtfa))

    if 'Sparge and Mash-out Water Volume' in recipe_config:
        smwv = config['unit'].convertUnits(recipe_config['Sparge and Mash-out Water Volume'], 'gallons')
        print 'Begin heating sparge and mash-out water: {0:.2f} gallons.'.format(smwv)
        smwv = config['unit'].convertUnits(smwv, 'gallons', 'liters')
        if mtfa is None:
            mowtm = (mttm + mwtm + gtm) * (sparge_temp - mtf) / (boiling_temp - sparge_temp)
        else:
            mowtm = (mttm + mwtm + gtm) * (sparge_temp - mtfa) / (boiling_temp - sparge_temp)
            
        mowv = mowtm / (water_specific_heat * water_density)

        swv = smwv - mowv
        swtm = swv * water_density * water_specific_heat
        swt = (hlttm * (sparge_temp - ambient_temp) + swtm * sparge_temp) / swtm
        
        print 'When water reaches {0:.1f} degF, transfer {1:.1f} gallons to the hot liquor tank.'.format(celsius_to_fahrenheit(swt), config['unit'].convertUnits(swv, 'liters', 'gallons'))
        print 'Bring remaining (mash-out) water, {0:.1f} gallons, to a boil.'.format(config['unit'].convertUnits(mowv, 'liters', 'gallons'))
        print 'Add mash-out water to mash, bringing temperature up to {0:.1f} degF.'.format(celsius_to_fahrenheit(sparge_temp))


    recipe_config['Water Temperature in Kettle'] = celsius_to_fahrenheit(wtik)
    recipe_config['Water Temperature in Mashtun'] = celsius_to_fahrenheit(wtita)
    recipe_config['Final Mash Temperature'] = celsius_to_fahrenheit(mtf)
    
    return config, recipe_config

def get_common_params(config, recipe_config):
    if 'Brew Day' in recipe_config and 'temperature' in recipe_config['Brew Day']:
        ambient_temp = fahrenheit_to_celsius(recipe_config['Brew Day']['temperature'])
    else:
        ambient_temp = fahrenheit_to_celsius(65)
        print 'Ambient temperature on brew day not specified; assuming {0:.0f} degF.'.format(celsius_to_fahrenheit(ambient_temp))

    if 'Mash Water Volume' in recipe_config:
        mwv = config['unit'].convertUnits(recipe_config['Mash Water Volume'], 'liters')
    else:
        print 'Mash Water Volume not specified, try running malt_composition first.'
        sys.exit()

    grain_mass = 0.
    if 'Malt' in recipe_config:
        for malt in recipe_config['Malt']:
            if 'mass' in malt:
                grain_mass += config['unit'].convertUnits(malt['mass'], 'kilograms')

    if grain_mass == 0:
        print "No grain mass specified. That's a weak beer!"
        sys.exit()

    if 'Water Density' in config:
        water_density = config['unit'].convertUnits(config['Water Density'], 'kilograms_per_liter')
    else:
        water_density = 1. # kilograms per liter

    if 'Water Specific Heat' in config:
        water_specific_heat = config['unit'].convertUnits(config['Water Specific Heat'], "calories_per_kilogram_per_degC")
    else:
        water_specific_heat = 1000. # calories per kg per degC

    if 'Grain Specific Heat' in config:
        grain_specific_heat = config['unit'].convertUnits(config['Grain Specific Heat'], "calories_per_kilogram_per_degC")
    else:
        grain_specific_heat = 396.8068 # calories per kg per degC

    if 'Mashtun Thermal Mass' in config:
        mttm = config['unit'].convertUnits(config['Mashtun Thermal Mass'], "calories_per_degC")
    else:
        mttm = 1362.152 # calories per degC

    if 'Hot Liquor Tank Thermal Mass' in config:
        hlttm = config['unit'].convertUnits(config['Hot Liquor Tank Thermal Mass'], "calories_per_degC")
    else:
        print 'Assuming Hot Liquor Tank Thermal Mass is the same as the Mashtun Thermal Mass.'
        hlttm = mttm

    # Heat loss during transfer from brew kettle to mash tun
    if 'Heat Loss During Kettle Transfer' in config:
        hldt = config['unit'].convertUnits(config['Heat Loss During Kettle Transfer'], "degC")
    else:
        hldt = config['unit'].convertUnits("5.2 degF", "degC")

    # Heat Loss In Tun: temperature drop before adding grain (error margin)
    if 'Heat Loss in Mashtun' in config:
        hlit = config['unit'].convertUnits(config['Heat Loss in Mashtun'], "degC")
    else:
        hlit = config['unit'].convertUnits("1 degF", "degC")

    if 'Mash Cooling Rate' in config:
        mcr = config['unit'].convertUnits(config['Mash Cooling Rate'], "degC_per_hour")
    else:
        mcr = config['unit'].convertUnits("4 degF_per_hour", "degC_per_hour")

    if 'Sparge Temperature' in config:
        sparge_temp = fahrenheit_to_celsius(config['Sparge Temperature'])
    else:
        sparge_temp = fahrenheit_to_celsius(170)
        print 'Assuming Sparge Temperature is {0:.1f} degF.'.format(celsius_to_fahrenheit(sparge_temp))

    if 'Boiling Temperature' in config:
        boiling_temp = fahrenheit_to_celsius(config['Boiling Temperature'])
    else:
        boiling_temp = fahrenheit_to_celsius(212)
        print 'Assuming Boiling Temperature is {0:.1f} degF.'.format(celsius_to_fahrenheit(boiling_temp))

    gtm = grain_mass * grain_specific_heat
    return ambient_temp, mwv, gtm, water_density, water_specific_heat, mttm, hlttm, hldt, hlit, mcr, sparge_temp, boiling_temp

def fahrenheit_to_celsius(degf, difference=False):
    if difference:
        return (5. / 9.) * degf
    else:
        return (5. / 9.) * (degf - 32.)

def celsius_to_fahrenheit(degc, difference=False):
    if difference:
        return (9. / 5.) * degc
    else:
        return (9. / 5.) * degc + 32

if __name__ == '__main__':
    config = json.load(open('/Users/bobwilson/beer/bin/homebrew.json', 'r'))
    unit = units()
    unit.parseUnitFile(config['files']['units'])
    config['unit'] = unit

    parser = argparse.ArgumentParser()
    parser.add_argument('recipe', type=str, help='Recipe JSON')
    parser.add_argument('-o', '--output', type=str, help='Output file')

    args = parser.parse_args()
    recipe_config = json.load(open(args.recipe, 'r'))
    if args.output:
        config['Output'] = args.output

    execute(config, recipe_config)



