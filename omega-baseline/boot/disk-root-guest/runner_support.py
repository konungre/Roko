"""Root/data attachment composition only. No process or VM is started here."""
import image
import data_image

def attach(command,root_fd,data_fd=None,phase='none'):
    if phase not in ('none','read','write') or ((data_fd is None)!=(phase=='none')):
        raise ValueError('Explicit optional data phase/descriptor required')
    forbidden={'-blockdev','-drive','-hda','-hdb','-hdc','-hdd','-cdrom','-virtfs','-fsdev'}
    if forbidden.intersection(command) or command.count('-append')!=1 or '-nic' not in command or command[command.index('-nic')+1]!='none':
        raise ValueError('Expected clean network-disabled QEMU command')
    out=list(command);pos=out.index('-append')+1
    if 'roko.root-data=' in out[pos]:raise ValueError('Duplicate root data phase')
    out[pos]+=' roko.root-data='+phase
    out+=image.attach(root_fd)  # Must be first: immutable root is vda.
    if data_fd is not None:out+=data_image.attach(data_fd)  # Optional controller is vdb.
    return out
